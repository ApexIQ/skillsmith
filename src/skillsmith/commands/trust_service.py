from __future__ import annotations

import hashlib
import json
import hmac
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import click

from . import console

SERVICE_DIR_NAME = ".agent/service"
SERVICE_FILE_NAME = "trust.json"
AUTHORITY_FILE_NAME = "trust-authority.json"
AUTHORITY_SYNC_DIR_NAME = ".agent/trust/authority"
AUTHORITY_BOOTSTRAP_FILE_NAME = "bootstrap.json"
AUTHORITY_BUNDLE_FILE_NAME = "bundle.json"
AUTHORITY_REVOCATIONS_FILE_NAME = "revocations.json"
SERVICE_NAME = "trust"
SERVICE_VERSION = 1
AUTHORITY_SERVICE_NAME = "trust-authority"
AUTHORITY_SERVICE_VERSION = 1
AUTHORITY_SIGNATURE_ALGO = "hmac-sha256"


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
    handler.send_header("WWW-Authenticate", 'Bearer realm="skillsmith-trust"')
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


def _load_authority_state_from_server(handler: BaseHTTPRequestHandler) -> dict:
    authority_path = Path(getattr(handler.server, "authority_path"))
    lock = getattr(handler.server, "state_lock")
    with lock:
        return _load_authority_state(authority_path)


def _save_authority_state(handler: BaseHTTPRequestHandler, payload: dict) -> dict:
    authority_path = Path(getattr(handler.server, "authority_path"))
    lock = getattr(handler.server, "state_lock")
    with lock:
        normalized = _normalize_authority_state(payload)
        normalized["generated_at"] = _timestamp_to_string()
        _write_authority_state(authority_path, normalized)
        return normalized


class _TrustServiceHandler(BaseHTTPRequestHandler):
    server_version = "skillsmith-trust/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if not _authorized(self):
            return
        segments = _split_path(self.path)
        if segments == ["health"]:
            _json_response(self, HTTPStatus.OK, {"service": SERVICE_NAME, "status": "ok"})
            return
        if segments == ["trust", "authority", "bootstrap"]:
            payload = _load_authority_state_from_server(self)
            _json_response(self, HTTPStatus.OK, _authority_bootstrap_payload(payload))
            return
        if segments == ["trust"]:
            _json_response(self, HTTPStatus.OK, _load_state_from_server(self))
            return
        if len(segments) >= 5 and segments[0] == "trust" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            if len(segments) == 6 and segments[5] == "keys":
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "keys": _keys_for_team(payload, tenant_id=tenant_id, team_id=team_id)})
                return
            if len(segments) == 7 and segments[5] == "keys":
                key_id = segments[6]
                payload = _load_state_from_server(self)
                key = _find_key(payload.get("keys", []), tenant_id, team_id, key_id)
                if key is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "key not found")
                    return
                _json_response(self, HTTPStatus.OK, _normalize_key(key))
                return
            if len(segments) == 8 and segments[5] == "keys" and segments[7] == "history":
                key_id = segments[6]
                payload = _load_state_from_server(self)
                key = _find_key(payload.get("keys", []), tenant_id, team_id, key_id)
                if key is None:
                    _error_response(self, HTTPStatus.NOT_FOUND, "key not found")
                    return
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "key_id": key_id, "history": list(key.get("history", []))})
                return
            if len(segments) == 6 and segments[5] == "revocations":
                payload = _load_state_from_server(self)
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {"tenant_id": tenant_id, "team_id": team_id, "revocations": _revocations_for_team(payload, tenant_id=tenant_id, team_id=team_id)},
                )
                return
            if len(segments) == 6 and segments[5] == "history":
                payload = _load_state_from_server(self)
                _json_response(self, HTTPStatus.OK, {"tenant_id": tenant_id, "team_id": team_id, "history": _history_for_team(payload, tenant_id=tenant_id, team_id=team_id)})
                return
        if len(segments) >= 6 and segments[:2] == ["trust", "authority"] and segments[2] == "tenants" and segments[4] == "teams":
            tenant_id = segments[3]
            team_id = segments[5]
            if len(segments) == 7 and segments[6] == "bundle":
                payload = _load_state_from_server(self)
                state = _load_authority_state_from_server(self)
                bundle = _authority_bundle_payload(payload, tenant_id=tenant_id, team_id=team_id)
                bundle["signature"] = _authority_signature(bundle, state["trust_roots"][0])
                _json_response(self, HTTPStatus.OK, bundle)
                return
            if len(segments) == 7 and segments[6] == "revocations":
                payload = _load_state_from_server(self)
                state = _load_authority_state_from_server(self)
                revocations = _authority_revocations_payload(payload, tenant_id=tenant_id, team_id=team_id)
                revocations["signature"] = _authority_signature(revocations, state["trust_roots"][0])
                _json_response(self, HTTPStatus.OK, revocations)
                return
        _error_response(self, HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if not _authorized(self):
            return
        segments = _split_path(self.path)
        if len(segments) >= 6 and segments[0] == "trust" and segments[1] == "tenants" and segments[3] == "teams":
            tenant_id = segments[2]
            team_id = segments[4]
            payload = _load_state_from_server(self)
            body = _parse_request_body(self)
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
) -> ThreadingHTTPServer:
    project_root = Path.cwd() if cwd is None else Path(cwd)
    state_path = _state_path(project_root)
    authority_path = _authority_state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if not state_path.exists():
        _write_json(state_path, _empty_state())
    if not authority_path.exists():
        _write_authority_state(authority_path, _empty_authority_state())
    server = ThreadingHTTPServer((host, port), _TrustServiceHandler)
    server.state_path = str(state_path)  # type: ignore[attr-defined]
    server.authority_path = str(authority_path)  # type: ignore[attr-defined]
    server.state_lock = threading.Lock()  # type: ignore[attr-defined]
    auth_token = str(bearer_token if bearer_token is not None else token if token is not None else "skillsmith-local-token").strip()
    server.bearer_token = auth_token  # type: ignore[attr-defined]
    return server


def start_trust_service(
    cwd: Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    bearer_token: str | None = None,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = create_trust_service_server(cwd, host=host, port=port, token=token, bearer_token=bearer_token)
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
) -> None:
    server = create_trust_service_server(cwd, host=host, port=port, token=token, bearer_token=bearer_token)
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
def trust_service_serve_command(cwd: Path, host: str, port: int, bearer_token: str) -> None:
    run_trust_service(cwd, host=host, port=port, bearer_token=bearer_token)


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
