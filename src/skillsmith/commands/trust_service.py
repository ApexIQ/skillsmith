from __future__ import annotations

import base64
import hashlib
import json
import hmac
import re
import sqlite3
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import click

from . import console

SERVICE_DIR_NAME = ".agent/service"
SERVICE_FILE_NAME = "trust.json"
SERVICE_DB_FILE_NAME = "trust.sqlite3"
AUTHORITY_FILE_NAME = "trust-authority.json"
AUTHORITY_DB_FILE_NAME = "trust-authority.sqlite3"
AUTHORITY_SYNC_DIR_NAME = ".agent/trust/authority"
AUTHORITY_BOOTSTRAP_FILE_NAME = "bootstrap.json"
AUTHORITY_BUNDLE_FILE_NAME = "bundle.json"
AUTHORITY_REVOCATIONS_FILE_NAME = "revocations.json"
SERVICE_NAME = "trust"
SERVICE_VERSION = 1
AUTHORITY_SERVICE_NAME = "trust-authority"
AUTHORITY_SERVICE_VERSION = 1
AUTHORITY_SIGNATURE_ALGO = "hmac-sha256"
SQLITE_STATE_TABLE_NAME = "service_state"
READ_ROLES = ("viewer", "editor", "approver", "admin")
WRITE_ROLES = ("editor", "admin")


@dataclass(frozen=True)
class _AuthClaims:
    token: str
    roles: tuple[str, ...]
    tenants: tuple[str, ...]
    team_scopes: tuple[tuple[str, tuple[str, ...]], ...]
    name: str = ""
    mode: str = "legacy"


@dataclass(frozen=True)
class _AuthContext:
    authenticated: bool
    token: str
    claims: _AuthClaims
    mode: str


@dataclass(frozen=True)
class _OidcConfig:
    issuer: str
    audience: str
    shared_secret: str
    algorithms: tuple[str, ...]
    subject_claim: str = "sub"
    name_claim: str = "email"
    roles_claim: str = "roles"
    groups_claim: str = "groups"
    tenants_claim: str = "tenants"
    teams_claim: str = "teams"
    group_role_map: dict[str, tuple[str, ...]] | None = None
    default_roles: tuple[str, ...] = ()


class _AuthoritySigner:
    provider_name = "unknown"

    def sign(self, payload: dict, root: dict) -> dict:
        raise NotImplementedError


class _LocalHmacAuthoritySigner(_AuthoritySigner):
    provider_name = "local-hmac"

    def sign(self, payload: dict, root: dict) -> dict:
        return _authority_signature(payload, root)


class _ExternalAuthoritySigner(_AuthoritySigner):
    provider_name = "external"

    def sign(self, payload: dict, root: dict) -> dict:
        raise NotImplementedError("external signer provider is not implemented")


def _timestamp_to_string(value: Any | None = None) -> str:
    from datetime import datetime, timezone

    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _service_root(cwd: Path) -> Path:
    return cwd / SERVICE_DIR_NAME


def _state_path(cwd: Path) -> Path:
    return _service_root(cwd) / SERVICE_FILE_NAME


def _authority_state_path(cwd: Path) -> Path:
    return _service_root(cwd) / AUTHORITY_FILE_NAME


def _authority_sync_root(cwd: Path) -> Path:
    return cwd / AUTHORITY_SYNC_DIR_NAME


def _resolve_project_path(cwd: Path, path: Path | None, default_name: str) -> Path:
    if path is None:
        return cwd / default_name
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return cwd / candidate


def _sqlite_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _sqlite_ensure_state_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SQLITE_STATE_TABLE_NAME} (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            payload TEXT NOT NULL
        )
        """
    )


def _sqlite_read_state(
    path: Path,
    *,
    default_factory: Callable[[], dict],
    normalize: Callable[[Any], dict],
) -> dict:
    if not path.exists():
        return default_factory()
    try:
        with _sqlite_connection(path) as connection:
            _sqlite_ensure_state_table(connection)
            row = connection.execute(f"SELECT payload FROM {SQLITE_STATE_TABLE_NAME} WHERE id = 1").fetchone()
            if row is None:
                return default_factory()
            payload = json.loads(str(row[0]))
    except Exception:
        return default_factory()
    if not isinstance(payload, dict):
        return default_factory()
    return normalize(payload)


def _sqlite_write_state(
    path: Path,
    payload: dict,
    *,
    normalize: Callable[[Any], dict],
) -> dict:
    normalized = normalize(payload)
    normalized["generated_at"] = _timestamp_to_string()
    serialized = json.dumps(normalized, indent=2, sort_keys=True)
    with _sqlite_connection(path) as connection:
        _sqlite_ensure_state_table(connection)
        connection.execute(
            f"INSERT OR REPLACE INTO {SQLITE_STATE_TABLE_NAME} (id, payload) VALUES (1, ?)",
            (serialized,),
        )
        connection.commit()
    return normalized


def _sqlite_initialize_state(
    path: Path,
    *,
    default_factory: Callable[[], dict],
    normalize: Callable[[Any], dict],
    legacy_path: Path | None = None,
    legacy_loader: Callable[[Path], dict] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _sqlite_connection(path) as connection:
        _sqlite_ensure_state_table(connection)
        row = connection.execute(f"SELECT 1 FROM {SQLITE_STATE_TABLE_NAME} WHERE id = 1").fetchone()
        if row is not None:
            return
        if legacy_path is not None and legacy_path.exists() and legacy_loader is not None:
            try:
                payload = legacy_loader(legacy_path)
            except Exception:
                payload = default_factory()
        else:
            payload = default_factory()
        normalized = normalize(payload)
        normalized["generated_at"] = str(normalized.get("generated_at", _timestamp_to_string()))
        connection.execute(
            f"INSERT OR REPLACE INTO {SQLITE_STATE_TABLE_NAME} (id, payload) VALUES (1, ?)",
            (json.dumps(normalized, indent=2, sort_keys=True),),
        )
        connection.commit()


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip().lower()).strip("-")
    return text or "key"


def _split_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = [values]
    items: list[str] = []
    for value in raw_values:
        for part in str(value).split(","):
            text = part.strip()
            if text and text not in items:
                items.append(text)
    return items


def _unique_values(values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in items:
            items.append(text)
    return items


def _normalize_role_values(values: Any) -> list[str]:
    roles: list[str] = []
    for value in _split_values(values):
        role = value.strip().lower()
        if role in READ_ROLES and role not in roles:
            roles.append(role)
    return roles


def _normalize_scope_values(values: Any) -> list[str]:
    scopes: list[str] = []
    for value in _split_values(values):
        scope = value.strip()
        if scope and scope not in scopes:
            scopes.append(scope)
    return scopes


def _normalize_team_scopes(values: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    scopes: list[tuple[str, tuple[str, ...]]] = []

    def add_scope(tenant: str, teams: Any) -> None:
        tenant_key = str(tenant).strip() or "*"
        team_values = tuple(_normalize_scope_values(teams) or ["*"])
        entry = (tenant_key, team_values)
        if entry not in scopes:
            scopes.append(entry)

    if isinstance(values, dict):
        for tenant, teams in values.items():
            add_scope(str(tenant), teams)
    elif isinstance(values, list):
        for value in values:
            if isinstance(value, dict):
                tenant = value.get("tenant", value.get("tenant_id", value.get("scope", "*")))
                teams = value.get("teams", value.get("team_scopes", value.get("team_ids", [])))
                add_scope(str(tenant), teams)
            else:
                text = str(value).strip()
                if not text:
                    continue
                if "/" in text:
                    tenant, team = text.split("/", 1)
                    add_scope(tenant, [team])
                else:
                    add_scope("*", [text])
    elif isinstance(values, str):
        text = values.strip()
        if text:
            if "/" in text:
                tenant, team = text.split("/", 1)
                add_scope(tenant, [team])
            else:
                add_scope("*", [text])

    return tuple(scopes)


def _legacy_claims(token: str) -> _AuthClaims:
    return _AuthClaims(
        token=token,
        roles=("admin",),
        tenants=("*",),
        team_scopes=(("*", ("*",)),),
        name="legacy-token",
        mode="legacy",
    )


def _public_claims() -> _AuthClaims:
    return _AuthClaims(
        token="",
        roles=("admin",),
        tenants=("*",),
        team_scopes=(("*", ("*",)),),
        name="anonymous",
        mode="public",
    )


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _load_oidc_config(path: Path | None) -> _OidcConfig | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OIDC config must be a JSON object")
    claims = payload.get("claims", {})
    if not isinstance(claims, dict):
        claims = {}
    raw_group_role_map = payload.get("group_role_map", {})
    group_role_map: dict[str, tuple[str, ...]] = {}
    if isinstance(raw_group_role_map, dict):
        for group_name, roles in raw_group_role_map.items():
            normalized_roles = tuple(_normalize_role_values(roles))
            if normalized_roles:
                group_role_map[str(group_name).strip()] = normalized_roles
    issuer = str(payload.get("issuer", "")).strip()
    audience = str(payload.get("audience", "")).strip()
    shared_secret = str(payload.get("shared_secret", "")).strip()
    if not issuer or not audience or not shared_secret:
        raise ValueError("OIDC config requires issuer, audience, and shared_secret")
    algorithms = tuple(str(value).strip() for value in _split_values(payload.get("algorithms", ["HS256"])) if str(value).strip())
    return _OidcConfig(
        issuer=issuer,
        audience=audience,
        shared_secret=shared_secret,
        algorithms=algorithms or ("HS256",),
        subject_claim=str(claims.get("subject", "sub")).strip() or "sub",
        name_claim=str(claims.get("name", "email")).strip() or "email",
        roles_claim=str(claims.get("roles", "roles")).strip() or "roles",
        groups_claim=str(claims.get("groups", "groups")).strip() or "groups",
        tenants_claim=str(claims.get("tenants", "tenants")).strip() or "tenants",
        teams_claim=str(claims.get("teams", "teams")).strip() or "teams",
        group_role_map=group_role_map,
        default_roles=tuple(_normalize_role_values(payload.get("default_roles", []))),
    )


def _token_from_header(handler: BaseHTTPRequestHandler) -> str:
    header = str(handler.headers.get("Authorization", "")).strip()
    if not header.startswith("Bearer "):
        return ""
    return header.removeprefix("Bearer ").strip()


def _oidc_claims(token: str, config: _OidcConfig) -> _AuthClaims | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    encoded_header, encoded_payload, encoded_signature = parts
    try:
        header = json.loads(_base64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return None
    algorithm = str(header.get("alg", "")).strip()
    if algorithm not in config.algorithms or algorithm != "HS256":
        return None
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(config.shared_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_signature = _base64url_decode(encoded_signature)
    except Exception:
        return None
    if not hmac.compare_digest(actual_signature, expected_signature):
        return None
    if str(payload.get("iss", "")).strip() != config.issuer:
        return None
    audience = payload.get("aud")
    if isinstance(audience, list):
        valid_audience = config.audience in [str(value).strip() for value in audience]
    else:
        valid_audience = str(audience or "").strip() == config.audience
    if not valid_audience:
        return None
    exp = payload.get("exp")
    if exp is not None:
        try:
            if float(exp) <= _timestamp_epoch():
                return None
        except Exception:
            return None
    subject = str(payload.get(config.subject_claim, payload.get("sub", ""))).strip()
    name = str(payload.get(config.name_claim, payload.get("email", subject))).strip() or subject
    roles = _normalize_role_values(payload.get(config.roles_claim, []))
    groups = _split_values(payload.get(config.groups_claim, []))
    for group_name in groups:
        roles.extend(list((config.group_role_map or {}).get(group_name, ())))
    roles = _unique_values([role.lower() for role in roles if role])
    if not roles:
        roles = list(config.default_roles)
    tenants = tuple(_normalize_scope_values(payload.get(config.tenants_claim, [])))
    team_scopes = _normalize_team_scopes(payload.get(config.teams_claim, []))
    return _AuthClaims(
        token=token,
        roles=tuple(roles),
        tenants=tenants,
        team_scopes=team_scopes,
        name=name,
        mode="oidc",
    )


def _timestamp_epoch() -> float:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).timestamp()


def _has_required_role(context: _AuthContext, required_roles: tuple[str, ...]) -> bool:
    current_roles = {role.lower() for role in context.claims.roles}
    if "admin" in current_roles:
        return True
    return any(role.lower() in current_roles for role in required_roles)


def _tenant_allowed(context: _AuthContext, tenant_id: str) -> bool:
    tenant = tenant_id.strip().lower()
    tenants = {value.strip().lower() for value in context.claims.tenants}
    return "*" in tenants or tenant in tenants


def _team_allowed(context: _AuthContext, tenant_id: str, team_id: str) -> bool:
    tenant = tenant_id.strip().lower()
    team = team_id.strip().lower()
    for scope_tenant, teams in context.claims.team_scopes:
        tenant_scope = scope_tenant.strip().lower()
        team_scopes = {value.strip().lower() for value in teams}
        if tenant_scope not in {"*", tenant}:
            continue
        if "*" in team_scopes or team in team_scopes or f"{tenant}/{team}" in team_scopes:
            return True
    return False


def _scope_allowed(context: _AuthContext, tenant_id: str, team_id: str) -> bool:
    return _tenant_allowed(context, tenant_id) and _team_allowed(context, tenant_id, team_id)


def _key_visible_to_context(entry: dict, context: _AuthContext) -> bool:
    if context.mode in {"legacy", "public"} and context.claims.roles == ("admin",):
        return True
    return _scope_allowed(context, str(entry.get("tenant_id", "")), str(entry.get("team_id", "")))


def _trust_view(payload: dict, context: _AuthContext) -> dict:
    normalized = _normalize_state(payload)
    if context.mode in {"legacy", "public"} and context.claims.roles == ("admin",):
        return normalized
    normalized["keys"] = [entry for entry in normalized.get("keys", []) if _key_visible_to_context(entry, context)]
    normalized["revocations"] = [entry for entry in normalized.get("revocations", []) if _key_visible_to_context(entry, context)]
    return normalized


def _normalize_public_key(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    modulus = str(raw.get("n", raw.get("modulus", raw.get("public_key", "")))).strip().lower().removeprefix("0x")
    exponent = raw.get("e", raw.get("exponent", 65537))
    if not modulus:
        return {}
    try:
        exponent_value = int(str(exponent).strip(), 0)
    except Exception:
        exponent_value = 65537
    if exponent_value <= 0:
        exponent_value = 65537
    return {"n": modulus, "e": exponent_value}


def _empty_state() -> dict:
    now = _timestamp_to_string()
    return {"service": SERVICE_NAME, "version": SERVICE_VERSION, "generated_at": now, "keys": [], "revocations": []}


def _normalize_authority_root(entry: dict, *, now: str | None = None) -> dict:
    normalized = dict(entry)
    current_time = now or _timestamp_to_string()
    key_id = str(normalized.get("key_id", "")).strip() or _slugify(str(normalized.get("name", "root")))
    algorithm = str(normalized.get("algorithm", AUTHORITY_SIGNATURE_ALGO)).strip().lower() or AUTHORITY_SIGNATURE_ALGO
    secret = str(normalized.get("secret", normalized.get("material", normalized.get("key", "")))).strip()
    if not secret:
        return {}
    normalized.update(
        {
            "key_id": key_id,
            "name": str(normalized.get("name", key_id)).strip() or key_id,
            "algorithm": algorithm,
            "secret": secret,
            "status": str(normalized.get("status", "active")).strip().lower() or "active",
            "created_at": str(normalized.get("created_at", current_time)),
            "updated_at": str(normalized.get("updated_at", current_time)),
        }
    )
    return normalized


def _empty_authority_state() -> dict:
    now = _timestamp_to_string()
    return {
        "service": AUTHORITY_SERVICE_NAME,
        "version": AUTHORITY_SERVICE_VERSION,
        "generated_at": now,
        "authority_id": "local",
        "trust_roots": [
            {
                "key_id": "root-1",
                "name": "root-1",
                "algorithm": AUTHORITY_SIGNATURE_ALGO,
                "secret": "skillsmith-local-authority-root",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    }


def _normalize_authority_state(payload: Any) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    normalized = dict(payload)
    roots = normalized.get("trust_roots", [])
    if not isinstance(roots, list):
        roots = []
    normalized["service"] = AUTHORITY_SERVICE_NAME
    normalized["version"] = AUTHORITY_SERVICE_VERSION
    normalized["generated_at"] = str(normalized.get("generated_at", _timestamp_to_string()))
    normalized["authority_id"] = str(normalized.get("authority_id", "local")).strip() or "local"
    normalized_roots = [_normalize_authority_root(entry) for entry in roots if isinstance(entry, dict)]
    normalized["trust_roots"] = [entry for entry in normalized_roots if entry]
    if not normalized["trust_roots"]:
        normalized["trust_roots"] = _empty_authority_state()["trust_roots"]
    return normalized


def _load_authority_state(path: Path) -> dict:
    if not path.exists():
        return _empty_authority_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_authority_state()
    return _normalize_authority_state(payload)


def _write_authority_state(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_authority_state(payload)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)
    return path


def _authority_root_by_key_id(state: dict) -> dict[str, dict]:
    return {
        str(root.get("key_id", "")).strip().lower(): root
        for root in state.get("trust_roots", [])
        if isinstance(root, dict) and str(root.get("key_id", "")).strip()
    }


def _canonical_authority_payload(payload: dict) -> bytes:
    signable = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _authority_signature(payload: dict, root: dict) -> dict:
    secret = str(root.get("secret", "")).strip()
    key_id = str(root.get("key_id", "")).strip()
    digest = hashlib.sha256(_canonical_authority_payload(payload)).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "algorithm": AUTHORITY_SIGNATURE_ALGO,
        "key_id": key_id,
        "digest": digest,
        "signature": signature,
        "signed_at": _timestamp_to_string(),
    }


def _authority_bundle_payload(payload: dict, *, tenant_id: str, team_id: str) -> dict:
    return {
        "service": AUTHORITY_SERVICE_NAME,
        "version": AUTHORITY_SERVICE_VERSION,
        "generated_at": _timestamp_to_string(),
        "tenant_id": tenant_id,
        "team_id": team_id,
        "keys": _keys_for_team(payload, tenant_id=tenant_id, team_id=team_id),
    }


def _authority_revocations_payload(payload: dict, *, tenant_id: str, team_id: str) -> dict:
    return {
        "service": AUTHORITY_SERVICE_NAME,
        "version": AUTHORITY_SERVICE_VERSION,
        "generated_at": _timestamp_to_string(),
        "tenant_id": tenant_id,
        "team_id": team_id,
        "revocations": _revocations_for_team(payload, tenant_id=tenant_id, team_id=team_id),
    }


def _authority_bootstrap_payload(state: dict) -> dict:
    return {
        "service": AUTHORITY_SERVICE_NAME,
        "version": AUTHORITY_SERVICE_VERSION,
        "generated_at": str(state.get("generated_at", _timestamp_to_string())),
        "authority_id": str(state.get("authority_id", "local")).strip() or "local",
        "trust_roots": [dict(root) for root in state.get("trust_roots", []) if isinstance(root, dict)],
    }


def _normalize_key(entry: dict, *, now: str | None = None) -> dict:
    normalized = dict(entry)
    current_time = now or _timestamp_to_string()
    tenant_id = str(normalized.get("tenant_id", "")).strip()
    team_id = str(normalized.get("team_id", "")).strip()
    key_id = str(normalized.get("key_id", "")).strip() or _slugify(str(normalized.get("name", "key")))
    algorithm = str(normalized.get("algorithm", "hmac-sha256")).strip().lower() or "hmac-sha256"
    status = str(normalized.get("status", "active")).strip().lower() or "active"
    kind = str(normalized.get("kind", "shared-secret" if algorithm.startswith("hmac") else "public-key")).strip().lower()
    history = [item for item in normalized.get("history", []) if isinstance(item, dict)]

    normalized.update(
        {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "key_id": key_id,
            "name": str(normalized.get("name", key_id)).strip() or key_id,
            "algorithm": algorithm,
            "kind": kind,
            "status": status,
            "history": history,
            "published_at": str(normalized.get("published_at", current_time)),
            "updated_at": str(normalized.get("updated_at", current_time)),
        }
    )
    if "material" in normalized and normalized["material"] is not None:
        normalized["material"] = str(normalized["material"])
    if "public_key" in normalized:
        normalized["public_key"] = _normalize_public_key(normalized.get("public_key"))
    return normalized


def _normalize_state(payload: Any) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    normalized = dict(payload)
    keys = normalized.get("keys", [])
    revocations = normalized.get("revocations", [])
    if not isinstance(keys, list):
        keys = []
    if not isinstance(revocations, list):
        revocations = []
    normalized["service"] = SERVICE_NAME
    normalized["version"] = SERVICE_VERSION
    normalized["generated_at"] = str(normalized.get("generated_at", _timestamp_to_string()))
    normalized["keys"] = [_normalize_key(entry) for entry in keys if isinstance(entry, dict)]
    normalized["revocations"] = [dict(entry) for entry in revocations if isinstance(entry, dict)]
    return normalized


def _load_json(path: Path) -> dict:
    if not path.exists():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    return _normalize_state(payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_state(payload)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)
    return path


def _find_key(keys: list[dict], tenant_id: str, team_id: str, key_id: str) -> dict | None:
    target_tenant = tenant_id.strip().lower()
    target_team = team_id.strip().lower()
    target_key = key_id.strip().lower()
    for entry in keys:
        if (
            str(entry.get("tenant_id", "")).strip().lower() == target_tenant
            and str(entry.get("team_id", "")).strip().lower() == target_team
            and str(entry.get("key_id", "")).strip().lower() == target_key
        ):
            return entry
    return None


def _append_history(entry: dict, *, action: str, actor: str, from_state: str | None, to_state: str | None, note: str | None = None) -> None:
    event = {
        "action": action,
        "actor": actor,
        "at": _timestamp_to_string(),
        "from_state": from_state,
        "to_state": to_state,
    }
    if note:
        event["note"] = note
    entry.setdefault("history", []).append(event)


def _ensure_key(
    payload: dict,
    *,
    tenant_id: str,
    team_id: str,
    body: dict,
    actor: str,
    action: str,
) -> dict:
    now = _timestamp_to_string()
    keys = payload.setdefault("keys", [])
    key_id = str(body.get("key_id", body.get("name", ""))).strip() or _slugify(str(body.get("name", "key")))
    current = _find_key(keys, tenant_id, team_id, key_id)
    previous_state = None
    if current is None:
        current = {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "key_id": key_id,
            "history": [],
            "published_at": now,
        }
        keys.append(current)
        previous_state = None
    else:
        previous_state = str(current.get("status", "active"))

    algorithm = str(body.get("algorithm", current.get("algorithm", "hmac-sha256"))).strip().lower() or "hmac-sha256"
    kind = str(body.get("kind", current.get("kind", "shared-secret" if algorithm.startswith("hmac") else "public-key"))).strip().lower()
    current.update(
        {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "key_id": key_id,
            "name": str(body.get("name", current.get("name", key_id))).strip() or key_id,
            "algorithm": algorithm,
            "kind": kind,
            "status": "active",
            "updated_at": now,
        }
    )
    if body.get("material") not in (None, ""):
        current["material"] = str(body["material"])
        current.pop("public_key", None)
    if body.get("public_key") is not None:
        current["public_key"] = _normalize_public_key(body.get("public_key"))
        current.pop("material", None)
    if body.get("previous_key_id") not in (None, ""):
        current["previous_key_id"] = str(body["previous_key_id"]).strip()
    if body.get("note") not in (None, ""):
        current["note"] = str(body["note"]).strip()

    _append_history(current, action=action, actor=actor, from_state=previous_state, to_state="active", note=str(body.get("note", "")).strip() or None)
    return current


def _revoke_key(payload: dict, *, tenant_id: str, team_id: str, key_id: str, actor: str, reason: str | None = None) -> dict:
    keys = payload.setdefault("keys", [])
    current = _find_key(keys, tenant_id, team_id, key_id)
    if current is None:
        current = {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "key_id": key_id,
            "history": [],
            "published_at": _timestamp_to_string(),
            "status": "revoked",
        }
        keys.append(current)
    previous_state = str(current.get("status", "active"))
    current["status"] = "revoked"
    current["revoked_at"] = _timestamp_to_string()
    current["updated_at"] = current["revoked_at"]
    if reason:
        current["revocation_reason"] = reason
    payload.setdefault("revocations", []).append(
        {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "key_id": key_id,
            "revoked_at": current["revoked_at"],
            "reason": reason or "",
            "actor": actor,
        }
    )
    _append_history(current, action="revoke", actor=actor, from_state=previous_state, to_state="revoked", note=reason)
    return current


def _rotate_key(
    payload: dict,
    *,
    tenant_id: str,
    team_id: str,
    body: dict,
    actor: str,
) -> tuple[dict, dict]:
    current_key_id = str(body.get("current_key_id", "")).strip()
    new_key_id = str(body.get("key_id", body.get("new_key_id", ""))).strip() or _slugify(str(body.get("name", "key")))
    current = _find_key(payload.setdefault("keys", []), tenant_id, team_id, current_key_id) if current_key_id else None
    if current is not None:
        previous_state = str(current.get("status", "active"))
        current["status"] = "rotated"
        current["rotated_at"] = _timestamp_to_string()
        current["updated_at"] = current["rotated_at"]
        _append_history(
            current,
            action="rotate-from",
            actor=actor,
            from_state=previous_state,
            to_state="rotated",
            note=str(body.get("note", "")).strip() or None,
        )
    rotated = _ensure_key(
        payload,
        tenant_id=tenant_id,
        team_id=team_id,
        body={**body, "key_id": new_key_id, "previous_key_id": current_key_id or None},
        actor=actor,
        action="rotate-to",
    )
    rotated["rotated_from_key_id"] = current_key_id or ""
    return current, rotated


def _keys_for_team(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    return [
        _normalize_key(entry)
        for entry in payload.get("keys", [])
        if str(entry.get("tenant_id", "")).strip().lower() == tenant_id.strip().lower()
        and str(entry.get("team_id", "")).strip().lower() == team_id.strip().lower()
    ]


def _revocations_for_team(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    return [
        dict(entry)
        for entry in payload.get("revocations", [])
        if str(entry.get("tenant_id", "")).strip().lower() == tenant_id.strip().lower()
        and str(entry.get("team_id", "")).strip().lower() == team_id.strip().lower()
    ]


def _history_for_team(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    events: list[dict] = []
    for key in _keys_for_team(payload, tenant_id=tenant_id, team_id=team_id):
        for event in key.get("history", []):
            events.append({**event, "tenant_id": tenant_id, "team_id": team_id, "key_id": key["key_id"]})
    return events


def _parse_request_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        return {}
    raw = handler.rfile.read(content_length)
    if not raw:
        return {}
    payload = json.loads(raw.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _error_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, message: str) -> None:
    _json_response(handler, status, {"error": message})


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(HTTPStatus.UNAUTHORIZED)
    handler.send_header("WWW-Authenticate", 'Bearer realm="skillsmith-trust"')
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    body = json.dumps({"error": "unauthorized"}).encode("utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _forbidden(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, HTTPStatus.FORBIDDEN, {"error": "forbidden"})


def _split_path(path: str) -> list[str]:
    segments = [segment for segment in urlparse(path).path.split("/") if segment]
    if segments and segments[0] == "v1":
        segments = segments[1:]
    return segments


def _authenticate(handler: BaseHTTPRequestHandler) -> _AuthContext | None:
    if _split_path(handler.path) == ["health"]:
        return _AuthContext(authenticated=False, token="", claims=_public_claims(), mode="public")
    server = handler.server
    oidc_config: _OidcConfig | None = getattr(server, "oidc_config", None)
    token = _token_from_header(handler)
    if oidc_config is not None:
        if not token:
            _unauthorized(handler)
            return None
        claims = _oidc_claims(token, oidc_config)
        if claims is None:
            _unauthorized(handler)
            return None
        return _AuthContext(authenticated=True, token=token, claims=claims, mode="oidc")
    expected = str(getattr(server, "bearer_token", "")).strip()
    if not expected:
        return _AuthContext(authenticated=False, token=token, claims=_public_claims(), mode="public")
    if token == expected:
        return _AuthContext(authenticated=True, token=token, claims=_legacy_claims(token), mode="legacy")
    _unauthorized(handler)
    return None


def _require_access(
    handler: BaseHTTPRequestHandler,
    context: _AuthContext,
    *,
    required_roles: tuple[str, ...] = READ_ROLES,
    tenant_id: str | None = None,
    team_id: str | None = None,
) -> bool:
    if not _has_required_role(context, required_roles):
        _forbidden(handler)
        return False
    if tenant_id is not None and team_id is not None and not _scope_allowed(context, tenant_id, team_id):
        _forbidden(handler)
        return False
    return True


def _sign_authority_payload(handler: BaseHTTPRequestHandler, payload: dict, root: dict) -> dict | None:
    signer: _AuthoritySigner = getattr(handler.server, "authority_signer")
    try:
        return signer.sign(payload, root)
    except NotImplementedError as exc:
        _error_response(handler, HTTPStatus.NOT_IMPLEMENTED, str(exc))
        return None


def _load_state_from_server(handler: BaseHTTPRequestHandler) -> dict:
    lock = getattr(handler.server, "state_lock")
    backend = str(getattr(handler.server, "backend", "json")).strip().lower()
    state_path = Path(getattr(handler.server, "state_path"))
    with lock:
        if backend == "sqlite":
            return _sqlite_read_state(state_path, default_factory=_empty_state, normalize=_normalize_state)
        return _load_json(state_path)


def _save_state(handler: BaseHTTPRequestHandler, payload: dict) -> dict:
    lock = getattr(handler.server, "state_lock")
    backend = str(getattr(handler.server, "backend", "json")).strip().lower()
    state_path = Path(getattr(handler.server, "state_path"))
    with lock:
        if backend == "sqlite":
            return _sqlite_write_state(state_path, payload, normalize=_normalize_state)
        normalized = _normalize_state(payload)
        normalized["generated_at"] = _timestamp_to_string()
        _write_json(state_path, normalized)
        return normalized


def _load_authority_state_from_server(handler: BaseHTTPRequestHandler) -> dict:
    lock = getattr(handler.server, "state_lock")
    backend = str(getattr(handler.server, "backend", "json")).strip().lower()
    authority_path = Path(getattr(handler.server, "authority_path"))
    with lock:
        if backend == "sqlite":
            return _sqlite_read_state(
                authority_path,
                default_factory=_empty_authority_state,
                normalize=_normalize_authority_state,
            )
        return _load_authority_state(authority_path)


def _save_authority_state(handler: BaseHTTPRequestHandler, payload: dict) -> dict:
    lock = getattr(handler.server, "state_lock")
    backend = str(getattr(handler.server, "backend", "json")).strip().lower()
    authority_path = Path(getattr(handler.server, "authority_path"))
    with lock:
        if backend == "sqlite":
            return _sqlite_write_state(authority_path, payload, normalize=_normalize_authority_state)
        normalized = _normalize_authority_state(payload)
        normalized["generated_at"] = _timestamp_to_string()
        _write_authority_state(authority_path, normalized)
        return normalized


class _TrustServiceHandler(BaseHTTPRequestHandler):
    server_version = "skillsmith-trust/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        segments = _split_path(self.path)
        if segments == ["health"]:
            _json_response(self, HTTPStatus.OK, {"service": SERVICE_NAME, "status": "ok"})
            return
        context = _authenticate(self)
        if context is None:
            return
        if segments == ["trust", "authority", "bootstrap"]:
            if not _require_access(self, context, required_roles=READ_ROLES):
                return
            payload = _load_authority_state_from_server(self)
            _json_response(self, HTTPStatus.OK, _authority_bootstrap_payload(payload))
            return
        if segments == ["trust"]:
            if not _require_access(self, context, required_roles=READ_ROLES):
                return
            _json_response(self, HTTPStatus.OK, _trust_view(_load_state_from_server(self), context))
            return
        if len(segments) >= 5 and segments[0] == "trust" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            if len(segments) == 6 and segments[5] == "keys":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "keys": _keys_for_team(payload, tenant_id=tenant_id, team_id=team_id)})
                return
            if len(segments) == 7 and segments[5] == "keys":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                key_id = segments[6]
                payload = _load_state_from_server(self)
                key = _find_key(payload.get("keys", []), tenant_id, team_id, key_id)
                if key is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "key not found")
                    return
                _json_response(self, HTTPStatus.OK, _normalize_key(key))
                return
            if len(segments) == 8 and segments[5] == "keys" and segments[7] == "history":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                key_id = segments[6]
                payload = _load_state_from_server(self)
                key = _find_key(payload.get("keys", []), tenant_id, team_id, key_id)
                if key is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "key not found")
                    return
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "key_id": key_id, "history": list(key.get("history", []))})
                return
            if len(segments) == 6 and segments[5] == "revocations":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {"tenant_id": tenant_id, "team_id": team_id, "revocations": _revocations_for_team(payload, tenant_id=tenant_id, team_id=team_id)},
                )
                return
            if len(segments) == 6 and segments[5] == "history":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "history": _history_for_team(payload, tenant_id=tenant_id, team_id=team_id)})
                return
        if len(segments) >= 6 and segments[:2] == ["trust", "authority"] and segments[2] == "tenants" and segments[4] == "teams":
            tenant_id = segments[3]
            team_id = segments[5]
            if len(segments) == 7 and segments[6] == "bundle":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                state = _load_authority_state_from_server(self)
                bundle = _authority_bundle_payload(payload, tenant_id=tenant_id, team_id=team_id)
                signature = _sign_authority_payload(self, bundle, state["trust_roots"][0])
                if signature is None:
                    return
                bundle["signature"] = signature
                _json_response(self, HTTPStatus.OK, bundle)
                return
            if len(segments) == 7 and segments[6] == "revocations":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                state = _load_authority_state_from_server(self)
                revocations = _authority_revocations_payload(payload, tenant_id=tenant_id, team_id=team_id)
                signature = _sign_authority_payload(self, revocations, state["trust_roots"][0])
                if signature is None:
                    return
                revocations["signature"] = signature
                _json_response(self, HTTPStatus.OK, revocations)
                return
        _error_response(self, HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        context = _authenticate(self)
        if context is None:
            return
        segments = _split_path(self.path)
        if len(segments) >= 6 and segments[0] == "trust" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            body = _parse_request_body(self)
            if not _require_access(self, context, required_roles=WRITE_ROLES, tenant_id=tenant_id, team_id=team_id):
                return
            payload = _load_state_from_server(self)
            actor = str(body.get("actor", "system")).strip() or "system"
            if len(segments) == 7 and segments[5] == "keys" and segments[6] == "publish":
                key = _ensure_key(payload, tenant_id=tenant_id, team_id=team_id, body=body, actor=actor, action="publish")
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"key": key, "state": saved})
                return
            if len(segments) == 7 and segments[5] == "keys" and segments[6] == "rotate":
                _, rotated = _rotate_key(payload, tenant_id=tenant_id, team_id=team_id, body=body, actor=actor)
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"key": rotated, "state": saved})
                return
            if len(segments) == 7 and segments[5] == "keys" and segments[6] == "revoke":
                key_id = str(body.get("key_id", body.get("name", ""))).strip() or _slugify(str(body.get("name", "key")))
                key = _revoke_key(payload, tenant_id=tenant_id, team_id=team_id, key_id=key_id, actor=actor, reason=str(body.get("reason", "")).strip() or None)
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"key": key, "state": saved})
                return
        _error_response(self, HTTPStatus.NOT_FOUND, "not found")


def create_trust_service_server(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    bearer_token: str | None = None,
    backend: str = "json",
    db_file: Path | None = None,
    authority_db_file: Path | None = None,
    oidc_config: Path | None = None,
    signer_provider: str = "local-hmac",
) -> ThreadingHTTPServer:
    project_root = Path.cwd() if cwd is None else Path(cwd)
    backend_name = str(backend).strip().lower() or "json"
    if backend_name not in {"json", "sqlite"}:
        raise ValueError(f"unsupported trust service backend: {backend}")
    resolved_oidc_config = _resolve_project_path(project_root, oidc_config, "trust-service-oidc.json") if oidc_config is not None else None
    oidc = _load_oidc_config(resolved_oidc_config)
    signer_name = str(signer_provider).strip().lower() or "local-hmac"
    if signer_name == "local-hmac":
        authority_signer: _AuthoritySigner = _LocalHmacAuthoritySigner()
    elif signer_name == "external":
        authority_signer = _ExternalAuthoritySigner()
    else:
        raise ValueError(f"unsupported signer provider: {signer_provider}")

    state_json_path = _state_path(project_root)
    authority_json_path = _authority_state_path(project_root)
    state_store_path = state_json_path
    authority_store_path = authority_json_path

    if backend_name == "sqlite":
        state_store_path = _resolve_project_path(project_root, db_file, SERVICE_DB_FILE_NAME)
        authority_store_path = _resolve_project_path(project_root, authority_db_file, AUTHORITY_DB_FILE_NAME)
        _sqlite_initialize_state(
            state_store_path,
            default_factory=_empty_state,
            normalize=_normalize_state,
            legacy_path=state_json_path,
            legacy_loader=_load_json,
        )
        _sqlite_initialize_state(
            authority_store_path,
            default_factory=_empty_authority_state,
            normalize=_normalize_authority_state,
            legacy_path=authority_json_path,
            legacy_loader=_load_authority_state,
        )
    else:
        state_store_path.parent.mkdir(parents=True, exist_ok=True)
        if not state_store_path.exists():
            _write_json(state_store_path, _empty_state())
        if not authority_store_path.exists():
            _write_authority_state(authority_store_path, _empty_authority_state())

    server = ThreadingHTTPServer((host, port), _TrustServiceHandler)
    server.backend = backend_name  # type: ignore[attr-defined]
    server.state_path = str(state_store_path)  # type: ignore[attr-defined]
    server.authority_path = str(authority_store_path)  # type: ignore[attr-defined]
    server.state_json_path = str(state_json_path)  # type: ignore[attr-defined]
    server.authority_json_path = str(authority_json_path)  # type: ignore[attr-defined]
    server.state_lock = threading.Lock()  # type: ignore[attr-defined]
    auth_token = str(bearer_token if bearer_token is not None else token if token is not None else "skillsmith-local-token").strip()
    server.bearer_token = auth_token  # type: ignore[attr-defined]
    server.oidc_config = oidc  # type: ignore[attr-defined]
    server.signer_provider = signer_name  # type: ignore[attr-defined]
    server.authority_signer = authority_signer  # type: ignore[attr-defined]
    return server


def start_trust_service(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    bearer_token: str | None = None,
    backend: str = "json",
    db_file: Path | None = None,
    authority_db_file: Path | None = None,
    oidc_config: Path | None = None,
    signer_provider: str = "local-hmac",
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = create_trust_service_server(
        cwd,
        host=host,
        port=port,
        token=token,
        bearer_token=bearer_token,
        backend=backend,
        db_file=db_file,
        authority_db_file=authority_db_file,
        oidc_config=oidc_config,
        signer_provider=signer_provider,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://{server.server_address[0]}:{server.server_address[1]}"


def run_trust_service(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    token: str | None = None,
    bearer_token: str | None = None,
    backend: str = "json",
    db_file: Path | None = None,
    authority_db_file: Path | None = None,
    oidc_config: Path | None = None,
    signer_provider: str = "local-hmac",
) -> None:
    server = create_trust_service_server(
        cwd,
        host=host,
        port=port,
        token=token,
        bearer_token=bearer_token,
        backend=backend,
        db_file=db_file,
        authority_db_file=authority_db_file,
        oidc_config=oidc_config,
        signer_provider=signer_provider,
    )
    console.print(f"[bold cyan]Trust service[/bold cyan] listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def pull_trust_snapshot(
    base_url: str,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str | None = None,
    team_id: str | None = None,
    timeout: float = 5.0,
) -> dict:
    auth_token = str(bearer_token if bearer_token is not None else token if token is not None else "").strip()
    root = base_url.rstrip("/")
    if tenant_id and team_id:
        url = f"{root}/v1/trust/tenants/{tenant_id}/teams/{team_id}/keys"
    else:
        url = f"{root}/v1/trust"
    request = Request(url, headers={"Authorization": f"Bearer {auth_token}"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trust snapshot response was not a JSON object")
    return payload


def _pull_json(base_url: str, path: str, *, token: str | None = None, bearer_token: str | None = None, timeout: float = 5.0) -> dict:
    auth_token = str(bearer_token if bearer_token is not None else token if token is not None else "").strip()
    root = base_url.rstrip("/")
    request = Request(f"{root}{path}", headers={"Authorization": f"Bearer {auth_token}"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trust service response was not a JSON object")
    return payload


def pull_trust_authority_bundle(
    base_url: str,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str,
    team_id: str,
    timeout: float = 5.0,
) -> dict:
    return _pull_json(
        base_url,
        f"/v1/trust/authority/tenants/{tenant_id}/teams/{team_id}/bundle",
        token=token,
        bearer_token=bearer_token,
        timeout=timeout,
    )


def pull_trust_authority_revocations(
    base_url: str,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str,
    team_id: str,
    timeout: float = 5.0,
) -> dict:
    return _pull_json(
        base_url,
        f"/v1/trust/authority/tenants/{tenant_id}/teams/{team_id}/revocations",
        token=token,
        bearer_token=bearer_token,
        timeout=timeout,
    )


def pull_trust_bootstrap(
    base_url: str,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    timeout: float = 5.0,
) -> dict:
    return _pull_json(base_url, "/v1/trust/authority/bootstrap", token=token, bearer_token=bearer_token, timeout=timeout)


def sync_trust_snapshot(
    base_url: str,
    destination: Path,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str | None = None,
    team_id: str | None = None,
    timeout: float = 5.0,
) -> Path:
    payload = pull_trust_snapshot(
        base_url,
        token=token,
        bearer_token=bearer_token,
        tenant_id=tenant_id,
        team_id=team_id,
        timeout=timeout,
    )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def sync_trust_authority_files(
    base_url: str,
    destination: Path,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str,
    team_id: str,
    timeout: float = 5.0,
) -> dict[str, Path]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    bootstrap = pull_trust_bootstrap(base_url, token=token, bearer_token=bearer_token, timeout=timeout)
    bundle = pull_trust_authority_bundle(
        base_url,
        token=token,
        bearer_token=bearer_token,
        tenant_id=tenant_id,
        team_id=team_id,
        timeout=timeout,
    )
    revocations = pull_trust_authority_revocations(
        base_url,
        token=token,
        bearer_token=bearer_token,
        tenant_id=tenant_id,
        team_id=team_id,
        timeout=timeout,
    )
    bootstrap_path = destination / AUTHORITY_BOOTSTRAP_FILE_NAME
    bundle_path = destination / AUTHORITY_BUNDLE_FILE_NAME
    revocations_path = destination / AUTHORITY_REVOCATIONS_FILE_NAME
    bootstrap_path.write_text(json.dumps(bootstrap, indent=2, sort_keys=True), encoding="utf-8")
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    revocations_path.write_text(json.dumps(revocations, indent=2, sort_keys=True), encoding="utf-8")
    return {"bootstrap": bootstrap_path, "bundle": bundle_path, "revocations": revocations_path}


@click.group(help="Run and synchronize the local trust service.", invoke_without_command=True)
@click.pass_context
def trust_service_command(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    console.print(ctx.get_help())


@trust_service_command.command("serve")
@click.option("--cwd", type=click.Path(path_type=Path, file_okay=False), default=".", show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8001, show_default=True, type=int)
@click.option("--token", "bearer_token", default="skillsmith-local-token", show_default=True)
@click.option("--backend", type=click.Choice(["json", "sqlite"], case_sensitive=False), default="json", show_default=True)
@click.option("--oidc-config", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Optional OIDC JWT validation config JSON file")
@click.option(
    "--signer-provider",
    type=click.Choice(["local-hmac", "external"], case_sensitive=False),
    default="local-hmac",
    show_default=True,
    help="Authority signature provider.",
)
@click.option(
    "--db-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="SQLite database file for trust state (sqlite backend only)",
)
@click.option(
    "--authority-db-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="SQLite database file for authority state (sqlite backend only)",
)
def trust_service_serve_command(
    cwd: Path,
    host: str,
    port: int,
    bearer_token: str,
    backend: str,
    oidc_config: Path | None,
    signer_provider: str,
    db_file: Path | None,
    authority_db_file: Path | None,
) -> None:
    run_trust_service(
        cwd,
        host=host,
        port=port,
        bearer_token=bearer_token,
        backend=backend,
        db_file=db_file,
        authority_db_file=authority_db_file,
        oidc_config=oidc_config,
        signer_provider=signer_provider,
    )


@trust_service_command.command("sync")
@click.argument("base_url")
@click.argument("destination", type=click.Path(path_type=Path))
@click.option("--token", "bearer_token", required=True, help="Bearer token used to authenticate against the service")
@click.option("--tenant-id", default=None, help="Optional tenant filter")
@click.option("--team-id", default=None, help="Optional team filter")
@click.option("--authority", is_flag=True, help="Fetch signed authority bootstrap, bundle, and revocation files instead of a snapshot.")
def trust_service_sync_command(
    base_url: str,
    destination: Path,
    bearer_token: str,
    tenant_id: str | None,
    team_id: str | None,
    authority: bool,
) -> None:
    if authority:
        if not tenant_id or not team_id:
            raise click.UsageError("--authority requires both --tenant-id and --team-id")
        paths = sync_trust_authority_files(
            base_url,
            destination,
            bearer_token=bearer_token,
            tenant_id=tenant_id,
            team_id=team_id,
        )
        console.print(
            f"[green]Synced trust authority files to {destination} "
            f"({paths['bootstrap'].name}, {paths['bundle'].name}, {paths['revocations'].name})[/green]"
        )
        return
    path = sync_trust_snapshot(
        base_url,
        destination,
        bearer_token=bearer_token,
        tenant_id=tenant_id,
        team_id=team_id,
    )
    console.print(f"[green]Synced trust snapshot to {path}[/green]")
