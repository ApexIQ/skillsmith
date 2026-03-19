from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import click
from rich.console import Console

console = Console()

SERVICE_DIR_NAME = ".agent/service"
SERVICE_FILE_NAME = "registry.json"
DEFAULT_AUTHZ_FILE_NAME = ".agent/service/registry-authz.json"
SERVICE_NAME = "registry"
SERVICE_VERSION = 1
AUTHZ_ROLES = ("viewer", "editor", "approver", "admin")
READ_ROLES = ("viewer", "editor", "approver", "admin")
WRITE_ROLES = ("editor", "admin")
APPROVAL_ROLES = ("approver", "admin")


@dataclass(frozen=True)
class _AuthClaims:
    token: str
    roles: tuple[str, ...]
    tenants: tuple[str, ...]
    team_scopes: tuple[tuple[str, tuple[str, ...]], ...]
    name: str = ""
    mode: str = "policy"


@dataclass(frozen=True)
class _AuthContext:
    authenticated: bool
    token: str
    claims: _AuthClaims
    mode: str


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


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip().lower()).strip("-")
    return text or "entry"


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
    roles = []
    for value in _split_values(values):
        role = value.strip().lower()
        if role in AUTHZ_ROLES and role not in roles:
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


def _normalize_claims(token: str, raw: Any) -> _AuthClaims | None:
    if not isinstance(raw, dict):
        return None
    roles = tuple(_normalize_role_values(raw.get("roles", raw.get("role", []))))
    tenants = tuple(_normalize_scope_values(raw.get("tenants", raw.get("tenant_scopes", raw.get("tenant_ids", [])))))
    team_scopes = _normalize_team_scopes(raw.get("teams", raw.get("team_scopes", raw.get("team_ids", []))))
    name = str(raw.get("name", raw.get("label", ""))).strip()
    return _AuthClaims(token=str(token), roles=roles, tenants=tenants, team_scopes=team_scopes, name=name)


def _load_authz_policy(path: Path | None) -> dict[str, _AuthClaims]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("tokens"), dict):
        payload = payload["tokens"]
    if not isinstance(payload, dict):
        return {}
    policy: dict[str, _AuthClaims] = {}
    for token, raw_claims in payload.items():
        claims = _normalize_claims(str(token), raw_claims)
        if claims is not None:
            policy[str(token)] = claims
    return policy


def _resolve_project_path(cwd: Path, path: Path | None, default_name: str) -> Path:
    if path is None:
        return cwd / default_name
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return cwd / candidate


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


def _empty_state() -> dict:
    now = _timestamp_to_string()
    return {"service": SERVICE_NAME, "version": SERVICE_VERSION, "generated_at": now, "entries": [], "skills": []}


def _normalize_entry(entry: dict, *, now: str | None = None) -> dict:
    normalized = dict(entry)
    current_time = now or _timestamp_to_string()
    tenant_id = str(normalized.get("tenant_id", "")).strip()
    team_id = str(normalized.get("team_id", "")).strip()
    name = str(normalized.get("name", "")).strip()
    entry_id = str(normalized.get("entry_id", "")).strip() or _slugify(name or "entry")
    owners = _split_values(normalized.get("owners", normalized.get("owner", [])))
    tags = _split_values(normalized.get("tags", []))
    approvals = [item for item in normalized.get("approvals", []) if isinstance(item, dict)]
    change_history = [item for item in normalized.get("change_history", []) if isinstance(item, dict)]

    normalized.update(
        {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "entry_id": entry_id,
            "name": name or entry_id,
            "description": str(normalized.get("description", "")).strip(),
            "source": str(normalized.get("source", "manual")).strip() or "manual",
            "lifecycle_state": str(normalized.get("lifecycle_state", normalized.get("state", "draft"))).strip().lower() or "draft",
            "approval_status": str(normalized.get("approval_status", "not_requested")).strip().lower() or "not_requested",
            "owners": owners,
            "tags": tags,
            "approvals": approvals,
            "change_history": change_history,
            "created_at": str(normalized.get("created_at", current_time)),
            "updated_at": str(normalized.get("updated_at", current_time)),
        }
    )
    normalized["state"] = normalized["lifecycle_state"]
    return normalized


def _normalize_state(payload: Any) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    normalized = dict(payload)
    entries = normalized.get("entries", normalized.get("skills", []))
    if not isinstance(entries, list):
        entries = []
    normalized["service"] = SERVICE_NAME
    normalized["version"] = SERVICE_VERSION
    normalized["generated_at"] = str(normalized.get("generated_at", _timestamp_to_string()))
    normalized["entries"] = [_normalize_entry(entry) for entry in entries if isinstance(entry, dict)]
    normalized["skills"] = list(normalized["entries"])
    return normalized


def _public_claims() -> _AuthClaims:
    return _AuthClaims(
        token="",
        roles=("admin",),
        tenants=("*",),
        team_scopes=(("*", ("*",)),),
        name="anonymous",
        mode="public",
    )


def _legacy_claims(token: str) -> _AuthClaims:
    return _AuthClaims(
        token=token,
        roles=("admin",),
        tenants=("*",),
        team_scopes=(("*", ("*",)),),
        name="legacy-token",
        mode="legacy",
    )


def _auth_context_view(context: _AuthContext) -> dict[str, Any]:
    claims = context.claims
    return {
        "authenticated": context.authenticated,
        "mode": context.mode,
        "name": claims.name,
        "roles": list(claims.roles),
        "tenant_scopes": list(claims.tenants),
        "team_scopes": [
            {"tenant": tenant, "teams": list(teams)}
            for tenant, teams in claims.team_scopes
        ],
    }


def _token_from_header(handler: BaseHTTPRequestHandler) -> str:
    header = str(handler.headers.get("Authorization", "")).strip()
    if not header.startswith("Bearer "):
        return ""
    return header.removeprefix("Bearer ").strip()


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(HTTPStatus.UNAUTHORIZED)
    handler.send_header("WWW-Authenticate", 'Bearer realm="skillsmith-registry"')
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    body = json.dumps({"error": "unauthorized"}).encode("utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _forbidden(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, HTTPStatus.FORBIDDEN, {"error": "forbidden"})


def _is_read_role(context: _AuthContext) -> bool:
    roles = {role.lower() for role in context.claims.roles}
    return "admin" in roles or any(role in roles for role in READ_ROLES)


def _has_write_role(context: _AuthContext) -> bool:
    roles = {role.lower() for role in context.claims.roles}
    return "admin" in roles or any(role in roles for role in WRITE_ROLES)


def _has_approval_role(context: _AuthContext) -> bool:
    roles = {role.lower() for role in context.claims.roles}
    return "admin" in roles or any(role in roles for role in APPROVAL_ROLES)


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


def _visible_to_context(entry: dict, context: _AuthContext) -> bool:
    if not context.authenticated and context.mode == "public":
        return True
    return _scope_allowed(context, str(entry.get("tenant_id", "")), str(entry.get("team_id", "")))


def _registry_view(payload: dict, context: _AuthContext) -> dict:
    normalized = _normalize_state(payload)
    if context.mode in {"legacy", "public"} and context.claims.roles == ("admin",):
        return normalized
    visible_entries = [entry for entry in normalized.get("entries", []) if _visible_to_context(entry, context)]
    normalized["entries"] = visible_entries
    normalized["skills"] = list(visible_entries)
    return normalized


def _authenticate(handler: BaseHTTPRequestHandler) -> _AuthContext | None:
    if _split_path(handler.path) == ["health"]:
        return _AuthContext(authenticated=False, token="", claims=_public_claims(), mode="public")

    server = handler.server
    authz_enabled = bool(getattr(server, "authz_enabled", False))
    authz_policy: dict[str, _AuthClaims] = getattr(server, "authz_policy", {})
    expected = str(getattr(server, "bearer_token", "")).strip()
    token = _token_from_header(handler)

    if authz_enabled:
        if not token:
            _unauthorized(handler)
            return None
        claims = authz_policy.get(token)
        if claims is None:
            _unauthorized(handler)
            return None
        return _AuthContext(authenticated=True, token=token, claims=claims, mode="policy")

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
    required = {role.lower() for role in required_roles}
    if "admin" not in {role.lower() for role in context.claims.roles} and not any(role in {role.lower() for role in context.claims.roles} for role in required):
        _forbidden(handler)
        return False
    if tenant_id is not None and team_id is not None and not _scope_allowed(context, tenant_id, team_id):
        _forbidden(handler)
        return False
    return True


def _find_entry(entries: list[dict], tenant_id: str, team_id: str, entry_id: str) -> dict | None:
    target_tenant = tenant_id.strip().lower()
    target_team = team_id.strip().lower()
    target_entry = entry_id.strip().lower()
    for entry in entries:
        if (
            str(entry.get("tenant_id", "")).strip().lower() == target_tenant
            and str(entry.get("team_id", "")).strip().lower() == target_team
            and str(entry.get("entry_id", "")).strip().lower() == target_entry
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
        "approval_status": entry.get("approval_status", "not_requested"),
    }
    if note:
        event["note"] = note
    entry.setdefault("change_history", []).append(event)


def _append_approval(
    entry: dict,
    *,
    actor: str,
    decision: str,
    note: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
) -> None:
    approval = {
        "decision": decision,
        "actor": actor,
        "at": _timestamp_to_string(),
        "from_state": from_state,
        "to_state": to_state,
    }
    if note:
        approval["note"] = note
    entry.setdefault("approvals", []).append(approval)


def _upsert_entry(payload: dict, *, tenant_id: str, team_id: str, body: dict, actor: str) -> dict:
    now = _timestamp_to_string()
    entries = payload.setdefault("entries", [])
    entry_id = str(body.get("entry_id", body.get("name", ""))).strip() or _slugify(str(body.get("name", "entry")))
    current = _find_entry(entries, tenant_id, team_id, entry_id)
    previous_state = None
    if current is None:
        current = {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "entry_id": entry_id,
            "created_at": now,
            "approvals": [],
            "change_history": [],
        }
        entries.append(current)
        action = "create"
    else:
        previous_state = str(current.get("lifecycle_state", "draft"))
        action = "update"

    current.update(
        {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "entry_id": entry_id,
            "name": str(body.get("name", current.get("name", entry_id))).strip() or entry_id,
            "description": str(body.get("description", current.get("description", ""))).strip(),
            "source": str(body.get("source", current.get("source", "manual"))).strip() or "manual",
            "lifecycle_state": str(body.get("state", body.get("lifecycle_state", current.get("lifecycle_state", "draft")))).strip().lower() or "draft",
            "approval_status": str(body.get("approval_state", body.get("approval_status", current.get("approval_status", "not_requested")))).strip().lower()
            or "not_requested",
            "owners": _split_values(body.get("owners", current.get("owners", []))),
            "tags": _split_values(body.get("tags", current.get("tags", []))),
            "updated_at": now,
        }
    )
    if body.get("notes") not in (None, ""):
        current["notes"] = str(body["notes"]).strip()

    if current["lifecycle_state"] == "approved" and current["approval_status"] == "not_requested":
        current["approval_status"] = "approved"
    elif current["lifecycle_state"] == "deprecated" and current["approval_status"] == "not_requested":
        current["approval_status"] = "withdrawn"

    _append_history(
        current,
        action=action,
        actor=actor,
        from_state=previous_state,
        to_state=current["lifecycle_state"],
        note=str(body.get("notes", "")).strip() or None,
    )
    return current


def _request_approval(entry: dict, *, actor: str, note: str | None = None) -> dict:
    previous_state = str(entry.get("lifecycle_state", "draft"))
    entry["approval_status"] = "pending"
    entry["updated_at"] = _timestamp_to_string()
    _append_history(entry, action="request-approval", actor=actor, from_state=previous_state, to_state=previous_state, note=note)
    return entry


def _approve(entry: dict, *, actor: str, note: str | None = None, decision: str = "approved") -> dict:
    previous_state = str(entry.get("lifecycle_state", "draft"))
    entry["approval_status"] = "approved" if decision == "approved" else decision
    if decision == "approved":
        entry["lifecycle_state"] = "approved"
    entry["updated_at"] = _timestamp_to_string()
    _append_approval(
        entry,
        actor=actor,
        decision=decision,
        note=note,
        from_state=previous_state,
        to_state=entry["lifecycle_state"],
    )
    _append_history(entry, action=decision, actor=actor, from_state=previous_state, to_state=entry["lifecycle_state"], note=note)
    return entry


def _history_view(entry: dict) -> list[dict]:
    return list(entry.get("change_history", []))


def _approvals_view(entry: dict) -> list[dict]:
    return list(entry.get("approvals", []))


def _team_entries(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    entries = payload.get("entries", [])
    return [
        _normalize_entry(entry)
        for entry in entries
        if str(entry.get("tenant_id", "")).strip().lower() == tenant_id.strip().lower()
        and str(entry.get("team_id", "")).strip().lower() == team_id.strip().lower()
    ]


def _team_approvals(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    approvals: list[dict] = []
    for entry in _team_entries(payload, tenant_id=tenant_id, team_id=team_id):
        for approval in _approvals_view(entry):
            approvals.append({**approval, "entry_id": entry["entry_id"], "tenant_id": tenant_id, "team_id": team_id})
    return approvals


def _team_history(payload: dict, *, tenant_id: str, team_id: str) -> list[dict]:
    events: list[dict] = []
    for entry in _team_entries(payload, tenant_id=tenant_id, team_id=team_id):
        for event in _history_view(entry):
            events.append({**event, "entry_id": entry["entry_id"], "tenant_id": tenant_id, "team_id": team_id})
    return events


def _project_root(path: Path) -> Path:
    return path if path.is_dir() else path.parent


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


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if _split_path(handler.path) == ["health"]:
        return True
    expected = str(getattr(handler.server, "bearer_token", "")).strip()
    if not expected:
        return True
    header = str(handler.headers.get("Authorization", "")).strip()
    if header == f"Bearer {expected}":
        return True
    handler.send_response(HTTPStatus.UNAUTHORIZED)
    handler.send_header("WWW-Authenticate", 'Bearer realm="skillsmith-registry"')
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    body = json.dumps({"error": "unauthorized"}).encode("utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return False


def _split_path(path: str) -> list[str]:
    segments = [segment for segment in urlparse(path).path.split("/") if segment]
    if segments and segments[0] == "v1":
        segments = segments[1:]
    return segments


def _load_state_from_server(handler: BaseHTTPRequestHandler) -> dict:
    state_path = Path(getattr(handler.server, "state_path"))
    lock = getattr(handler.server, "state_lock")
    with lock:
        return _load_json(state_path)


def _save_state(handler: BaseHTTPRequestHandler, payload: dict) -> dict:
    state_path = Path(getattr(handler.server, "state_path"))
    lock = getattr(handler.server, "state_lock")
    with lock:
        normalized = _normalize_state(payload)
        normalized["generated_at"] = _timestamp_to_string()
        _write_json(state_path, normalized)
        return normalized


class _RegistryServiceHandler(BaseHTTPRequestHandler):
    server_version = "skillsmith-registry/1.0"

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
        if segments == ["whoami"]:
            _json_response(self, HTTPStatus.OK, {"service": SERVICE_NAME, "auth": _auth_context_view(context)})
            return
        if segments == ["registry"]:
            if not _require_access(self, context, required_roles=READ_ROLES):
                return
            payload = _load_state_from_server(self)
            _json_response(self, HTTPStatus.OK, _registry_view(payload, context))
            return
        if len(segments) >= 5 and segments[0] == "registry" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            if len(segments) == 6 and segments[5] == "entries":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "entries": _team_entries(payload, tenant_id=tenant_id, team_id=team_id)})
                return
            if len(segments) == 7 and segments[5] == "entries":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                payload = _load_state_from_server(self)
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                _json_response(self, HTTPStatus.OK, _normalize_entry(entry))
                return
            if len(segments) == 8 and segments[5] == "entries" and segments[7] == "approvals":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                payload = _load_state_from_server(self)
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "entry_id": entry_id, "approvals": _approvals_view(entry)})
                return
            if len(segments) == 8 and segments[5] == "entries" and segments[7] == "history":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                payload = _load_state_from_server(self)
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "entry_id": entry_id, "history": _history_view(entry)})
                return
            if len(segments) == 6 and segments[5] == "approvals":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "approvals": _team_approvals(payload, tenant_id=tenant_id, team_id=team_id)})
                return
            if len(segments) == 6 and segments[5] == "history":
                if not _require_access(self, context, required_roles=READ_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "history": _team_history(payload, tenant_id=tenant_id, team_id=team_id)})
                return
        _error_response(self, HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        segments = _split_path(self.path)
        context = _authenticate(self)
        if context is None:
            return
        if len(segments) >= 6 and segments[0] == "registry" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            payload = _load_state_from_server(self)
            body = _parse_request_body(self)
            actor = str(body.get("actor", "system")).strip() or "system"
            if len(segments) == 6 and segments[5] == "entries":
                if not _require_access(self, context, required_roles=WRITE_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry = _upsert_entry(payload, tenant_id=tenant_id, team_id=team_id, body=body, actor=actor)
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"entry": entry, "state": saved})
                return
            if len(segments) == 7 and segments[5] == "entries":
                if not _require_access(self, context, required_roles=WRITE_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                previous_state = str(entry.get("lifecycle_state", "draft"))
                entry.update(
                    {
                        "name": str(body.get("name", entry.get("name", entry_id))).strip() or entry_id,
                        "description": str(body.get("description", entry.get("description", ""))).strip(),
                        "source": str(body.get("source", entry.get("source", "manual"))).strip() or "manual",
                        "lifecycle_state": str(body.get("state", body.get("lifecycle_state", entry.get("lifecycle_state", "draft")))).strip().lower() or "draft",
                        "approval_status": str(
                            body.get("approval_state", body.get("approval_status", entry.get("approval_status", "not_requested")))
                        ).strip().lower()
                        or "not_requested",
                        "owners": _split_values(body.get("owners", entry.get("owners", []))),
                        "tags": _split_values(body.get("tags", entry.get("tags", []))),
                        "updated_at": _timestamp_to_string(),
                    }
                )
                _append_history(
                    entry,
                    action="update",
                    actor=actor,
                    from_state=previous_state,
                    to_state=entry["lifecycle_state"],
                    note=str(body.get("notes", "")).strip() or None,
                )
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"entry": _normalize_entry(entry), "state": saved})
                return
            if len(segments) == 8 and segments[5] == "entries" and segments[7] == "request-approval":
                if not _require_access(self, context, required_roles=WRITE_ROLES, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                note = str(body.get("note", body.get("reason", ""))).strip() or None
                _request_approval(entry, actor=actor, note=note)
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"entry": _normalize_entry(entry), "state": saved})
                return
            if len(segments) == 8 and segments[5] == "entries" and segments[7] == "approvals":
                decision = str(body.get("decision", "approved")).strip().lower() or "approved"
                note = str(body.get("note", body.get("reason", ""))).strip() or None
                if decision == "pending":
                    required_roles = WRITE_ROLES
                elif decision in {"approved", "rejected", "withdrawn"}:
                    required_roles = APPROVAL_ROLES
                else:
                    _error_response(self, HTTPStatus.BAD_REQUEST, "decision must be pending, approved, rejected, or withdrawn")
                    return
                if not _require_access(self, context, required_roles=required_roles, tenant_id=tenant_id, team_id=team_id):
                    return
                entry_id = segments[6]
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                if decision == "pending":
                    _request_approval(entry, actor=actor, note=note)
                else:
                    _approve(entry, actor=actor, note=note, decision=decision)
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"entry": _normalize_entry(entry), "state": saved})
                return
            if len(segments) == 8 and segments[5] == "entries" and segments[7] == "history":
                entry_id = segments[6]
                entry = _find_entry(payload.get("entries", []), tenant_id, team_id, entry_id)
                if entry is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "entry not found")
                    return
                action = str(body.get("action", "note")).strip() or "note"
                from_state = body.get("from_state")
                to_state = body.get("to_state", entry.get("lifecycle_state", "draft"))
                _append_history(
                    entry,
                    action=action,
                    actor=actor,
                    from_state=str(from_state).strip() if from_state not in (None, "") else None,
                    to_state=str(to_state).strip() if to_state not in (None, "") else None,
                    note=str(body.get("note", body.get("notes", ""))).strip() or None,
                )
                entry["updated_at"] = _timestamp_to_string()
                saved = _save_state(self, payload)
                _json_response(self, HTTPStatus.OK, {"entry": _normalize_entry(entry), "state": saved})
                return
        _error_response(self, HTTPStatus.NOT_FOUND, "not found")


def create_registry_service_server(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    authz_file: Path | None = None,
    token: str | None = None,
    bearer_token: str | None = None,
) -> ThreadingHTTPServer:
    project_root = Path.cwd() if cwd is None else Path(cwd)
    state_path = _state_path(project_root)
    authz_path = _resolve_project_path(project_root, authz_file, DEFAULT_AUTHZ_FILE_NAME)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if not state_path.exists():
        _write_json(state_path, _empty_state())
    server = ThreadingHTTPServer((host, port), _RegistryServiceHandler)
    server.state_path = str(state_path)  # type: ignore[attr-defined]
    server.state_lock = threading.Lock()  # type: ignore[attr-defined]
    auth_token = str(bearer_token if bearer_token is not None else token if token is not None else "skillsmith-local-token").strip()
    server.bearer_token = auth_token  # type: ignore[attr-defined]
    server.authz_file = str(authz_path)  # type: ignore[attr-defined]
    server.authz_enabled = authz_path.exists()  # type: ignore[attr-defined]
    server.authz_policy = _load_authz_policy(authz_path)  # type: ignore[attr-defined]
    return server


def start_registry_service(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    authz_file: Path | None = None,
    token: str | None = None,
    bearer_token: str | None = None,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = create_registry_service_server(
        cwd,
        host=host,
        port=port,
        authz_file=authz_file,
        token=token,
        bearer_token=bearer_token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://{server.server_address[0]}:{server.server_address[1]}"


def run_registry_service(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    authz_file: Path | None = None,
    token: str | None = None,
    bearer_token: str | None = None,
) -> None:
    server = create_registry_service_server(
        cwd,
        host=host,
        port=port,
        authz_file=authz_file,
        token=token,
        bearer_token=bearer_token,
    )
    console.print(f"[bold cyan]Registry service[/bold cyan] listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def pull_registry_snapshot(
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
        url = f"{root}/v1/registry/tenants/{tenant_id}/teams/{team_id}/entries"
    else:
        url = f"{root}/v1/registry"
    request = Request(url, headers={"Authorization": f"Bearer {auth_token}"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registry snapshot response was not a JSON object")
    return payload


def sync_registry_snapshot(
    base_url: str,
    destination: Path,
    *,
    token: str | None = None,
    bearer_token: str | None = None,
    tenant_id: str | None = None,
    team_id: str | None = None,
    timeout: float = 5.0,
) -> Path:
    payload = pull_registry_snapshot(
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


@click.group(help="Run and synchronize the local registry service.", invoke_without_command=True)
@click.pass_context
def registry_service_command(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    console.print(ctx.get_help())


@registry_service_command.command("serve")
@click.option("--cwd", type=click.Path(path_type=Path, file_okay=False), default=".", show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option(
    "--authz-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=DEFAULT_AUTHZ_FILE_NAME,
    show_default=True,
    help="Optional JSON authz policy file",
)
@click.option("--token", "bearer_token", default="skillsmith-local-token", show_default=True)
def registry_service_serve_command(cwd: Path, host: str, port: int, authz_file: Path, bearer_token: str) -> None:
    run_registry_service(cwd, host=host, port=port, authz_file=authz_file, bearer_token=bearer_token)


@registry_service_command.command("sync")
@click.argument("base_url")
@click.argument("destination", type=click.Path(path_type=Path))
@click.option("--token", "bearer_token", required=True, help="Bearer token used to authenticate against the service")
@click.option("--tenant-id", default=None, help="Optional tenant filter")
@click.option("--team-id", default=None, help="Optional team filter")
def registry_service_sync_command(
    base_url: str,
    destination: Path,
    bearer_token: str,
    tenant_id: str | None,
    team_id: str | None,
) -> None:
    path = sync_registry_snapshot(
        base_url,
        destination,
        bearer_token=bearer_token,
        tenant_id=tenant_id,
        team_id=team_id,
    )
    console.print(f"[green]Synced registry snapshot to {path}[/green]")
