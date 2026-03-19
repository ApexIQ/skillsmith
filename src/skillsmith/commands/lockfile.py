from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any


LOCKFILE_NAME = "skills.lock.json"
VERIFICATION_STALE_DAYS = 30
LOCKFILE_VERSION = 1
LOCKFILE_SCHEMA_VERSION = 2
LOCKFILE_SIGNATURE_ALGO = "hmac-sha256"
LOCKFILE_SIGNING_KEY_ENV = "SKILLSMITH_LOCKFILE_SIGNING_KEY"
LOCKFILE_SIGNING_KEY_ID_ENV = "SKILLSMITH_LOCKFILE_SIGNING_KEY_ID"
PUBLISHER_MANIFEST_NAME = "skillsmith.manifest.json"
PUBLISHER_SIGNATURE_NAME = "skillsmith.sig"
PUBLISHER_SIGNATURE_MODE_OPTIONAL = "optional"
PUBLISHER_SIGNATURE_MODE_REQUIRED = "required"
PUBLISHER_SIGNATURE_MODE_OFF = "off"
PUBLISHER_SIGNATURE_MODES = {
    PUBLISHER_SIGNATURE_MODE_OFF,
    PUBLISHER_SIGNATURE_MODE_OPTIONAL,
    PUBLISHER_SIGNATURE_MODE_REQUIRED,
}
PUBLISHER_SIGNATURE_KEY_ALGO = "hmac-sha256"
PUBLISHER_SIGNATURE_RSA_ALGO = "rsa-sha256"
PUBLISHER_SIGNATURE_SCHEME_AUTO = "auto"
PUBLISHER_SIGNATURE_SCHEME_HMAC = "hmac"
PUBLISHER_SIGNATURE_SCHEME_RSA = "rsa"
PUBLISHER_SIGNATURE_SCHEME_MODES = {
    PUBLISHER_SIGNATURE_SCHEME_AUTO,
    PUBLISHER_SIGNATURE_SCHEME_HMAC,
    PUBLISHER_SIGNATURE_SCHEME_RSA,
}
PUBLISHER_SIGNATURE_ALLOWED_ALGORITHMS = {
    PUBLISHER_SIGNATURE_KEY_ALGO,
    PUBLISHER_SIGNATURE_RSA_ALGO,
}
TRUST_DIR_NAME = ".agent"
TRUST_SUBDIR_NAME = "trust"
PUBLISHER_REVOCATIONS_NAME = "publisher_revocations.json"
TRANSPARENCY_LOG_NAME = "transparency_log.jsonl"
AUTHORITY_SYNC_DIR_NAME = "authority"
AUTHORITY_BOOTSTRAP_NAME = "bootstrap.json"
AUTHORITY_BUNDLE_NAME = "bundle.json"
AUTHORITY_REVOCATIONS_NAME = "revocations.json"
AUTHORITY_SIGNATURE_ALGO = "hmac-sha256"
_RSA_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _timestamp_to_string(value: datetime.datetime | None = None) -> str:
    timestamp = value or _utc_now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    return timestamp.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        timestamp = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    return timestamp.astimezone(datetime.timezone.utc)


def _normalize_reasons(reasons: Any) -> list[str]:
    if not isinstance(reasons, list):
        return []
    normalized = []
    for reason in reasons:
        text = str(reason).strip()
        if text:
            normalized.append(text)
    return normalized


def _reason_hash(reasons: Any) -> str:
    payload = json.dumps(_normalize_reasons(reasons), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def lockfile_signing_key() -> str:
    return str(os.environ.get(LOCKFILE_SIGNING_KEY_ENV, "")).strip()


def lockfile_signing_enabled() -> bool:
    return bool(lockfile_signing_key())


def _lockfile_signature_key_id(signing_key: str) -> str:
    explicit_key_id = str(os.environ.get(LOCKFILE_SIGNING_KEY_ID_ENV, "")).strip()
    if explicit_key_id:
        return explicit_key_id
    return _sha256_bytes(signing_key.encode("utf-8"))[:12]


def _canonical_lockfile_bytes(payload: dict) -> bytes:
    signable = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _signature_digest(payload: dict, signing_key: str) -> str:
    return hmac.new(signing_key.encode("utf-8"), _canonical_lockfile_bytes(payload), hashlib.sha256).hexdigest()


def sign_lockfile_payload(payload: dict, signing_key: str | None = None) -> dict | None:
    key = (signing_key or lockfile_signing_key()).strip()
    if not key:
        return None
    return {
        "algo": LOCKFILE_SIGNATURE_ALGO,
        "value": _signature_digest(payload, key),
        "signed_at": _timestamp_to_string(),
        "key_id": _lockfile_signature_key_id(key),
    }


def verify_lockfile_signature(payload: dict, signing_key: str | None = None) -> dict:
    key = (signing_key if signing_key is not None else lockfile_signing_key()).strip()
    if not key:
        return {"state": "skipped", "valid": True, "message": "signature verification skipped (no signing key configured)"}

    signature = payload.get("signature")
    if not isinstance(signature, dict):
        return {"state": "unsigned", "valid": False, "message": "lockfile signature missing while signing key is configured"}

    algo = str(signature.get("algo", "")).strip().lower()
    value = str(signature.get("value", "")).strip()
    if algo != LOCKFILE_SIGNATURE_ALGO:
        return {"state": "unsupported", "valid": False, "message": f"unsupported lockfile signature algorithm '{algo or 'unknown'}'"}
    if not value:
        return {"state": "invalid", "valid": False, "message": "lockfile signature value is empty"}

    expected = _signature_digest(payload, key)
    if hmac.compare_digest(value, expected):
        key_id = str(signature.get("key_id", "")).strip()
        return {
            "state": "valid",
            "valid": True,
            "message": f"lockfile signature valid ({LOCKFILE_SIGNATURE_ALGO}{f', key_id={key_id}' if key_id else ''})",
        }
    return {"state": "invalid", "valid": False, "message": "lockfile signature mismatch; lockfile content may be tampered"}


def _legacy_checksum_for_path(path: Path) -> str:
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return ""
    return _sha256_bytes(skill_md.read_bytes())


def _checksum_for_path(path: Path) -> str:
    if not path.exists() or not path.is_dir():
        return ""

    manifest: list[dict[str, str]] = []
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel_path = file_path.relative_to(path).as_posix()
        file_hash = _sha256_bytes(file_path.read_bytes())
        manifest.append({"path": rel_path, "sha256": file_hash})

    payload = json.dumps(manifest, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return _sha256_bytes(payload)


def _checksum_matches(path: Path, checksum: str) -> bool:
    if not checksum:
        return False
    current_checksum = _checksum_for_path(path)
    if current_checksum and current_checksum == checksum:
        return True
    # Backward compatibility: lockfiles written before schema_version=2 hashed only SKILL.md.
    legacy_checksum = _legacy_checksum_for_path(path)
    return bool(legacy_checksum and legacy_checksum == checksum)


def _normalize_publisher_keys(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = []
        for item in raw:
            if isinstance(item, dict):
                key_id = str(item.get("key_id", item.get("id", item.get("name", "")))).strip()
                key_value = str(
                    item.get("key", item.get("value", item.get("secret", item.get("material", item.get("public_key", "")))))
                ).strip()
                if key_id and key_value:
                    items.append((key_id, key_value))
            elif isinstance(item, str) and item.strip():
                text = item.strip()
                if "=" in text:
                    key_id, key_value = text.split("=", 1)
                elif ":" in text:
                    key_id, key_value = text.split(":", 1)
                else:
                    key_id, key_value = text, text
                key_id = key_id.strip()
                key_value = key_value.strip()
                if key_id and key_value:
                    items.append((key_id, key_value))
    else:
        return {}

    normalized: dict[str, str] = {}
    for key_id, key_value in items:
        key_id_text = str(key_id).strip()
        key_value_text = str(key_value).strip()
        if not key_id_text or not key_value_text:
            continue
        normalized[key_id_text] = key_value_text
    return normalized


def _normalize_publisher_public_keys(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = []
        for item in raw:
            if isinstance(item, dict):
                key_id = str(item.get("key_id", item.get("id", item.get("name", "")))).strip()
                key_value = item.get("public_key", item.get("key", item.get("value", item.get("n", ""))))
                if key_id and key_value:
                    items.append((key_id, key_value))
            elif isinstance(item, str) and item.strip():
                text = item.strip()
                if "=" in text:
                    key_id, key_value = text.split("=", 1)
                elif ":" in text:
                    key_id, key_value = text.split(":", 1)
                else:
                    key_id, key_value = text, text
                key_id = key_id.strip()
                key_value = key_value.strip()
                if key_id and key_value:
                    items.append((key_id, key_value))
    else:
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for key_id, key_value in items:
        key_id_text = str(key_id).strip()
        if not key_id_text:
            continue
        if isinstance(key_value, dict):
            modulus_text = str(
                key_value.get(
                    "n",
                    key_value.get(
                        "modulus",
                        key_value.get("public_key", key_value.get("value", key_value.get("key", ""))),
                    ),
                )
            ).strip()
            exponent_value = key_value.get("e", key_value.get("exponent", 65537))
        else:
            raw_text = str(key_value).strip()
            if not raw_text:
                continue
            if ":" in raw_text:
                modulus_text, exponent_text = raw_text.split(":", 1)
                exponent_value = exponent_text.strip() or 65537
            else:
                modulus_text = raw_text
                exponent_value = 65537
        modulus_text = modulus_text.strip().lower().removeprefix("0x")
        if not modulus_text:
            continue
        try:
            exponent_int = int(str(exponent_value).strip(), 0)
        except Exception:
            exponent_int = 65537
        if exponent_int <= 0:
            exponent_int = 65537
        normalized[key_id_text] = {"n": modulus_text, "e": exponent_int}
    return normalized


def _publisher_signature_mode(raw: Any) -> str:
    mode = str(raw or PUBLISHER_SIGNATURE_MODE_OPTIONAL).strip().lower()
    if mode not in PUBLISHER_SIGNATURE_MODES:
        return PUBLISHER_SIGNATURE_MODE_OPTIONAL
    return mode


def _publisher_signature_scheme_mode(raw: Any) -> str:
    mode = str(raw or PUBLISHER_SIGNATURE_SCHEME_AUTO).strip().lower().replace("_", "-")
    aliases = {
        "shared-secret": PUBLISHER_SIGNATURE_SCHEME_HMAC,
        "secret": PUBLISHER_SIGNATURE_SCHEME_HMAC,
        "hmac-sha256": PUBLISHER_SIGNATURE_SCHEME_HMAC,
        "public-key": PUBLISHER_SIGNATURE_SCHEME_RSA,
        "rsa-sha256": PUBLISHER_SIGNATURE_SCHEME_RSA,
    }
    mode = aliases.get(mode, mode)
    if mode not in PUBLISHER_SIGNATURE_SCHEME_MODES:
        return PUBLISHER_SIGNATURE_SCHEME_AUTO
    return mode


def _publisher_signature_algorithms(raw: Any) -> list[str]:
    if isinstance(raw, (list, tuple, set)):
        items = raw
    elif isinstance(raw, str):
        items = [part.strip() for part in raw.split(",")]
    else:
        items = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        algorithm = str(item).strip().lower().replace("_", "-")
        if algorithm == "hmac":
            algorithm = PUBLISHER_SIGNATURE_KEY_ALGO
        elif algorithm == "rsa":
            algorithm = PUBLISHER_SIGNATURE_RSA_ALGO
        if algorithm not in PUBLISHER_SIGNATURE_ALLOWED_ALGORITHMS or algorithm in seen:
            continue
        seen.add(algorithm)
        normalized.append(algorithm)
    return normalized or [PUBLISHER_SIGNATURE_KEY_ALGO, PUBLISHER_SIGNATURE_RSA_ALGO]


def _normalize_publisher_key_rotation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    rotation: dict[str, Any] = {}
    for field in ("current_key_id", "rotation_started_at", "rotated_at", "expires_at", "rotation_reason"):
        value = raw.get(field)
        if value not in (None, ""):
            rotation[field] = str(value).strip()

    previous = raw.get("previous_key_ids", raw.get("previous_keys", raw.get("legacy_key_ids", [])))
    if isinstance(previous, list):
        previous_ids = [str(item).strip() for item in previous if str(item).strip()]
    else:
        previous_ids = [item.strip() for item in str(previous).split(",") if item.strip()]
    if previous_ids:
        rotation["previous_key_ids"] = previous_ids

    grace_period = raw.get("rotation_grace_period_days", raw.get("grace_period_days", raw.get("retention_days")))
    if grace_period not in (None, ""):
        try:
            rotation["rotation_grace_period_days"] = max(0, int(grace_period))
        except Exception:
            pass
    return rotation


def _publisher_rsa_components(public_key: dict[str, Any]) -> tuple[int, int] | None:
    if not isinstance(public_key, dict):
        return None
    modulus_value = public_key.get("n", public_key.get("modulus", ""))
    exponent_value = public_key.get("e", public_key.get("exponent", 65537))
    modulus_text = str(modulus_value).strip().lower().removeprefix("0x")
    if not modulus_text:
        return None
    try:
        modulus = int(modulus_text, 16)
    except Exception:
        return None
    try:
        exponent = int(str(exponent_value).strip(), 0)
    except Exception:
        return None
    if modulus <= 0 or exponent <= 0:
        return None
    return modulus, exponent


def _verify_rsa_sha256_signature(signature_value: str, public_key: dict[str, Any], message: bytes) -> bool:
    components = _publisher_rsa_components(public_key)
    if components is None:
        return False
    modulus, exponent = components
    try:
        signature_bytes = bytes.fromhex(signature_value)
    except ValueError:
        return False
    key_length = (modulus.bit_length() + 7) // 8
    if key_length < len(_RSA_SHA256_PREFIX) + hashlib.sha256().digest_size + 11:
        return False
    if len(signature_bytes) > key_length:
        return False
    signature_bytes = signature_bytes.rjust(key_length, b"\x00")
    signature_value_int = int.from_bytes(signature_bytes, "big")
    decrypted = pow(signature_value_int, exponent, modulus).to_bytes(key_length, "big")
    digest = hashlib.sha256(message).digest()
    expected = b"\x00\x01" + (b"\xff" * (key_length - len(_RSA_SHA256_PREFIX) - len(digest) - 3)) + b"\x00" + _RSA_SHA256_PREFIX + digest
    return hmac.compare_digest(decrypted, expected)


def _publisher_manifest_files(path: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    if not path.exists() or not path.is_dir():
        return files
    for file_path in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        if file_path.name in {PUBLISHER_MANIFEST_NAME, PUBLISHER_SIGNATURE_NAME}:
            continue
        rel_path = file_path.relative_to(path).as_posix()
        files.append({"path": rel_path, "sha256": _sha256_bytes(file_path.read_bytes())})
    return files


def _canonical_publisher_manifest(path: Path) -> dict:
    return {"algorithm": "sha256", "files": _publisher_manifest_files(path)}


def _canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _load_json_file(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_json_payload(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _trust_root(cwd: Path) -> Path:
    return cwd / TRUST_DIR_NAME / TRUST_SUBDIR_NAME


def _project_root_for_skill_path(path: Path) -> Path | None:
    resolved = path.resolve()
    for ancestor in (resolved, *resolved.parents):
        if ancestor.name == TRUST_DIR_NAME:
            return ancestor.parent
    if len(resolved.parents) >= 3:
        return resolved.parents[2]
    if resolved.parent != resolved:
        return resolved.parent
    return None


def _extract_key_id(value: Any) -> str:
    if isinstance(value, dict):
        for field in ("key_id", "id", "name", "key"):
            text = str(value.get(field, "")).strip()
            if text:
                return text
        return ""
    return str(value).strip()


def _revoked_key_ids_from_payload(raw: Any) -> list[str]:
    revoked: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        key_id = _extract_key_id(value)
        if key_id and key_id not in seen:
            seen.add(key_id)
            revoked.append(key_id)

    if isinstance(raw, dict):
        for field in ("revoked_key_ids", "revoked_keys", "key_ids", "revocations"):
            value = raw.get(field)
            if isinstance(value, dict):
                for key, entry in value.items():
                    if isinstance(entry, dict):
                        revoked_flag = str(entry.get("revoked", entry.get("disabled", True))).strip().lower()
                        if revoked_flag in {"", "0", "false", "no"}:
                            continue
                        add(key)
                    elif entry in (False, None, "", 0):
                        continue
                    else:
                        add(key)
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    add(item)
            elif value not in (None, ""):
                add(value)

        metadata_keys = {
            "revoked_key_ids",
            "revoked_keys",
            "key_ids",
            "revocations",
            "generated_at",
            "generated_by",
            "updated_at",
            "version",
            "notes",
            "reason",
            "description",
        }
        for key, entry in raw.items():
            if key in metadata_keys:
                continue
            if isinstance(entry, dict):
                revoked_flag = str(entry.get("revoked", entry.get("disabled", True))).strip().lower()
                if revoked_flag not in {"", "0", "false", "no"}:
                    add(key)
            elif isinstance(entry, bool):
                if entry:
                    add(key)
            elif isinstance(entry, str):
                if entry.strip().lower() in {"revoked", "true", "yes", "1"}:
                    add(key)
            elif entry not in (None, "", [], {}):
                add(key)
    elif isinstance(raw, (list, tuple, set)):
        for item in raw:
            add(item)
    elif isinstance(raw, str):
        for part in raw.replace("\n", ",").replace("\r", ",").split(","):
            add(part)
    return revoked


def load_publisher_revocations(cwd: Path) -> dict:
    path = _trust_root(cwd) / PUBLISHER_REVOCATIONS_NAME
    summary = {
        "path": path.relative_to(cwd).as_posix(),
        "present": path.exists(),
        "valid": True,
        "revoked_key_ids": [],
        "revoked_key_count": 0,
        "issues": [],
    }
    if not path.exists():
        return summary

    raw = _load_json_payload(path)
    if raw is None:
        summary["valid"] = False
        summary["issues"].append(f"{PUBLISHER_REVOCATIONS_NAME} is not valid JSON")
        return summary
    if not isinstance(raw, (dict, list, tuple, set, str)):
        summary["valid"] = False
        summary["issues"].append(f"{PUBLISHER_REVOCATIONS_NAME} must contain an object, array, or string")
        return summary

    revoked_key_ids = _revoked_key_ids_from_payload(raw)
    summary["revoked_key_ids"] = revoked_key_ids
    summary["revoked_key_count"] = len(revoked_key_ids)
    return summary


def _authority_sync_root(cwd: Path) -> Path:
    return _trust_root(cwd) / AUTHORITY_SYNC_DIR_NAME


def _authority_path(cwd: Path, name: str) -> Path:
    return _authority_sync_root(cwd) / name


def _normalize_authority_root(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    secret = str(raw.get("secret", raw.get("material", raw.get("key", "")))).strip()
    key_id = str(raw.get("key_id", raw.get("id", raw.get("name", "")))).strip()
    algorithm = str(raw.get("algorithm", AUTHORITY_SIGNATURE_ALGO)).strip().lower() or AUTHORITY_SIGNATURE_ALGO
    if not key_id or not secret:
        return {}
    return {
        "key_id": key_id,
        "name": str(raw.get("name", key_id)).strip() or key_id,
        "algorithm": algorithm,
        "secret": secret,
        "status": str(raw.get("status", "active")).strip().lower() or "active",
    }


def _authority_bootstrap_summary(cwd: Path) -> tuple[dict, dict[str, dict[str, Any]]]:
    path = _authority_path(cwd, AUTHORITY_BOOTSTRAP_NAME)
    summary = {
        "path": path.relative_to(cwd).as_posix(),
        "present": path.exists(),
        "valid": True,
        "trust_roots": [],
        "trust_root_count": 0,
        "issues": [],
    }
    if not path.exists():
        return summary, {}

    raw = _load_json_payload(path)
    if raw is None:
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BOOTSTRAP_NAME} is not valid JSON")
        return summary, {}
    if not isinstance(raw, dict):
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BOOTSTRAP_NAME} must contain a JSON object")
        return summary, {}

    roots = raw.get("trust_roots", [])
    if not isinstance(roots, list):
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BOOTSTRAP_NAME} must contain trust_roots as a list")
        return summary, {}

    normalized_roots = []
    root_map: dict[str, dict[str, Any]] = {}
    for root in roots:
        normalized = _normalize_authority_root(root)
        if not normalized:
            continue
        normalized_roots.append(normalized)
        root_map[str(normalized["key_id"]).strip().lower()] = normalized

    if not normalized_roots:
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BOOTSTRAP_NAME} does not define any trust roots")
        return summary, {}

    summary["trust_roots"] = [
        {key: value for key, value in root.items() if key != "secret"}
        for root in normalized_roots
    ]
    summary["trust_root_count"] = len(normalized_roots)
    return summary, root_map


def _authority_payload_signature(payload: dict, roots: dict[str, dict[str, Any]]) -> tuple[dict, str | None]:
    signature = payload.get("signature")
    if not isinstance(signature, dict):
        return {"valid": False, "issues": ["signature object missing"], "signature": None}, None

    algo = str(signature.get("algorithm", "")).strip().lower()
    key_id = str(signature.get("key_id", "")).strip()
    digest = str(signature.get("digest", "")).strip()
    value = str(signature.get("signature", "")).strip()
    if algo != AUTHORITY_SIGNATURE_ALGO:
        return {"valid": False, "issues": [f"unsupported authority signature algorithm '{algo or 'unknown'}'"], "signature": signature}, key_id or None
    if not key_id:
        return {"valid": False, "issues": ["signature key_id is missing"], "signature": signature}, None
    root = roots.get(key_id.lower())
    if root is None:
        return {"valid": False, "issues": [f"signature key_id '{key_id}' is not present in the authority bootstrap"], "signature": signature}, key_id

    canonical = json.dumps({k: v for k, v in payload.items() if k != "signature"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    expected_digest = hashlib.sha256(canonical).hexdigest()
    if digest != expected_digest:
        return {"valid": False, "issues": ["authority signature digest mismatch"], "signature": signature}, key_id
    expected_value = hmac.new(root["secret"].encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    if not value:
        return {"valid": False, "issues": ["authority signature value is missing"], "signature": signature}, key_id
    if not hmac.compare_digest(value, expected_value):
        return {"valid": False, "issues": ["authority signature verification failed"], "signature": signature}, key_id
    return {"valid": True, "issues": [], "signature": signature}, key_id


def _authority_bundle_summary(cwd: Path, bootstrap_roots: dict[str, dict[str, Any]]) -> tuple[dict, dict[str, str], dict[str, dict[str, Any]]]:
    path = _authority_path(cwd, AUTHORITY_BUNDLE_NAME)
    summary = {
        "path": path.relative_to(cwd).as_posix(),
        "present": path.exists(),
        "valid": True,
        "tenant_id": None,
        "team_id": None,
        "trusted_publisher_key_ids": [],
        "trusted_publisher_public_key_ids": [],
        "signature": None,
        "issues": [],
    }
    if not path.exists():
        return summary, {}, {}

    raw = _load_json_payload(path)
    if raw is None:
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BUNDLE_NAME} is not valid JSON")
        return summary, {}, {}
    if not isinstance(raw, dict):
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BUNDLE_NAME} must contain a JSON object")
        return summary, {}, {}

    summary["tenant_id"] = str(raw.get("tenant_id", "")).strip() or None
    summary["team_id"] = str(raw.get("team_id", "")).strip() or None
    signature_result, key_id = _authority_payload_signature(raw, bootstrap_roots)
    summary["signature"] = signature_result.get("signature")
    if not signature_result.get("valid"):
        summary["valid"] = False
        summary["issues"].extend(signature_result.get("issues", []))
        return summary, {}, {}

    keys = raw.get("keys", [])
    if not isinstance(keys, list):
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_BUNDLE_NAME} must contain keys as a list")
        return summary, {}, {}

    trusted_publisher_keys = _normalize_publisher_keys(keys)
    trusted_publisher_public_keys = _normalize_publisher_public_keys(keys)
    summary["trusted_publisher_key_ids"] = list(trusted_publisher_keys.keys())
    summary["trusted_publisher_public_key_ids"] = list(trusted_publisher_public_keys.keys())
    summary["signature_key_id"] = key_id
    return summary, trusted_publisher_keys, trusted_publisher_public_keys


def _authority_revocations_summary(cwd: Path, bootstrap_roots: dict[str, dict[str, Any]]) -> dict:
    path = _authority_path(cwd, AUTHORITY_REVOCATIONS_NAME)
    summary = {
        "path": path.relative_to(cwd).as_posix(),
        "present": path.exists(),
        "valid": True,
        "tenant_id": None,
        "team_id": None,
        "revoked_key_ids": [],
        "signature": None,
        "issues": [],
    }
    if not path.exists():
        return summary

    raw = _load_json_payload(path)
    if raw is None:
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_REVOCATIONS_NAME} is not valid JSON")
        return summary
    if not isinstance(raw, dict):
        summary["valid"] = False
        summary["issues"].append(f"{AUTHORITY_REVOCATIONS_NAME} must contain a JSON object")
        return summary

    summary["tenant_id"] = str(raw.get("tenant_id", "")).strip() or None
    summary["team_id"] = str(raw.get("team_id", "")).strip() or None
    signature_result, key_id = _authority_payload_signature(raw, bootstrap_roots)
    summary["signature"] = signature_result.get("signature")
    if not signature_result.get("valid"):
        summary["valid"] = False
        summary["issues"].extend(signature_result.get("issues", []))
        return summary

    revoked_key_ids = _revoked_key_ids_from_payload(raw.get("revocations", raw))
    summary["revoked_key_ids"] = revoked_key_ids
    summary["revoked_key_count"] = len(revoked_key_ids)
    summary["signature_key_id"] = key_id
    return summary


def _collect_authority_trust_data(
    cwd: Path,
) -> tuple[dict, dict, dict, dict[str, str], dict[str, dict[str, Any]]]:
    bootstrap_summary, bootstrap_roots = _authority_bootstrap_summary(cwd)
    bundle_summary, bundle_hmac_keys, bundle_rsa_keys = _authority_bundle_summary(cwd, bootstrap_roots)
    authority_revocations_summary = _authority_revocations_summary(cwd, bootstrap_roots)
    return bootstrap_summary, bundle_summary, authority_revocations_summary, bundle_hmac_keys, bundle_rsa_keys


def _parse_log_entry_timestamp(entry: dict) -> str | None:
    for field in ("logged_at", "verified_at", "timestamp", "created_at"):
        timestamp = _parse_timestamp(entry.get(field))
        if timestamp is not None:
            return _timestamp_to_string(timestamp)
    return None


def load_transparency_log_health(cwd: Path) -> dict:
    path = _trust_root(cwd) / TRANSPARENCY_LOG_NAME
    summary = {
        "path": path.relative_to(cwd).as_posix(),
        "present": path.exists(),
        "valid": True,
        "entry_count": 0,
        "malformed_count": 0,
        "latest_entry": None,
        "issues": [],
    }
    if not path.exists():
        return summary

    latest_timestamp: datetime.datetime | None = None
    latest_entry: dict | None = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            raw_entry = json.loads(text)
        except Exception:
            summary["valid"] = False
            summary["malformed_count"] += 1
            continue
        if not isinstance(raw_entry, dict):
            summary["valid"] = False
            summary["malformed_count"] += 1
            continue
        summary["entry_count"] += 1
        entry_timestamp = None
        for field in ("logged_at", "verified_at", "timestamp", "created_at"):
            parsed = _parse_timestamp(raw_entry.get(field))
            if parsed is not None:
                entry_timestamp = parsed
                break
        if entry_timestamp is not None and (latest_timestamp is None or entry_timestamp >= latest_timestamp):
            latest_timestamp = entry_timestamp
            latest_entry = {
                "logged_at": _timestamp_to_string(entry_timestamp),
                "state": str(raw_entry.get("state", "")).strip() or None,
                "valid": raw_entry.get("valid"),
                "key_id": str(raw_entry.get("key_id", "")).strip() or None,
                "artifact_path": str(raw_entry.get("artifact_path", "")).strip() or None,
            }
    if summary["malformed_count"]:
        summary["issues"].append(f"{TRANSPARENCY_LOG_NAME} contains malformed entries")
    summary["latest_entry"] = latest_entry
    return summary


def load_trust_health(cwd: Path, profile: dict | None = None) -> dict:
    profile = profile or {}
    revocations = load_publisher_revocations(cwd)
    transparency_log = load_transparency_log_health(cwd)
    bootstrap_summary, bundle_summary, authority_revocations_summary, authority_hmac_keys, authority_rsa_keys = _collect_authority_trust_data(cwd)

    trusted_hmac_keys = _normalize_publisher_keys(profile.get("trusted_publisher_keys"))
    trusted_rsa_keys = _normalize_publisher_public_keys(profile.get("trusted_publisher_public_keys"))
    for key_id, value in authority_hmac_keys.items():
        trusted_hmac_keys.setdefault(key_id, value)
    for key_id, value in authority_rsa_keys.items():
        trusted_rsa_keys.setdefault(key_id, value)
    trusted_key_ids = sorted(set(trusted_hmac_keys.keys()) | set(trusted_rsa_keys.keys()))

    authority_revoked_key_ids = authority_revocations_summary.get("revoked_key_ids", []) if authority_revocations_summary.get("valid") else []
    revoked_key_ids = sorted(set(revocations["revoked_key_ids"]) | set(authority_revoked_key_ids))
    revoked_trusted_key_ids = sorted(set(revoked_key_ids) & set(trusted_key_ids)) if trusted_key_ids else []
    revocations["trusted_key_ids"] = trusted_key_ids
    revocations["revoked_trusted_key_ids"] = revoked_trusted_key_ids
    transparency_log["entry_count"] = int(transparency_log["entry_count"])
    authority_components = [bootstrap_summary, bundle_summary, authority_revocations_summary]
    authority_issues: list[str] = []
    for component in authority_components:
        authority_issues.extend(component.get("issues", []))
    authority = {
        "bootstrap": bootstrap_summary,
        "bundle": bundle_summary,
        "revocations": authority_revocations_summary,
        "present": any(component.get("present") for component in authority_components),
        "valid": not authority_issues,
        "issues": authority_issues,
        "trusted_publisher_key_ids": trusted_key_ids,
        "trusted_publisher_public_key_ids": sorted(set(trusted_rsa_keys.keys())),
        "revoked_key_ids": revoked_key_ids,
    }
    return {
        "revocations": revocations,
        "transparency_log": transparency_log,
        "authority": authority,
    }


def _append_transparency_log(cwd: Path, verification: dict, artifact_path: Path) -> None:
    trust_dir = _trust_root(cwd)
    trust_dir.mkdir(parents=True, exist_ok=True)
    path = trust_dir / TRANSPARENCY_LOG_NAME
    project_root = cwd.resolve()
    try:
        artifact_relpath = artifact_path.resolve().relative_to(project_root).as_posix()
    except Exception:
        artifact_relpath = artifact_path.as_posix()
    record = _clean_dict(
        {
            "logged_at": _timestamp_to_string(),
            "project_root": project_root.as_posix(),
            "artifact_path": artifact_relpath,
            "artifact_name": artifact_path.name,
            "state": verification.get("state"),
            "valid": verification.get("valid"),
            "mode": verification.get("mode"),
            "signature_scheme_mode": verification.get("signature_scheme_mode"),
            "algorithm": verification.get("algorithm"),
            "scheme": verification.get("scheme"),
            "method": verification.get("method"),
            "key_id": verification.get("key_id"),
            "message": verification.get("message"),
            "expected_manifest_sha256": verification.get("expected_manifest_sha256"),
            "manifest_path": verification.get("manifest_path"),
            "signature_path": verification.get("signature_path"),
            "revocation_status": verification.get("revocation_status"),
            "revoked_key_ids": verification.get("revoked_key_ids"),
        }
    )
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        log_file.write("\n")


def verify_remote_skill_artifact(path: Path, profile: dict | None = None, cwd: Path | None = None) -> dict:
    profile = profile or {}
    mode = _publisher_signature_mode(profile.get("publisher_verification_mode"))
    signature_scheme_mode = _publisher_signature_scheme_mode(profile.get("publisher_signature_scheme_mode"))
    allowed_algorithms = _publisher_signature_algorithms(profile.get("publisher_signature_algorithms"))
    trusted_keys = _normalize_publisher_keys(profile.get("trusted_publisher_keys"))
    trusted_public_keys = _normalize_publisher_public_keys(profile.get("trusted_publisher_public_keys"))
    key_rotation = _normalize_publisher_key_rotation(profile.get("publisher_key_rotation"))
    project_root = cwd or _project_root_for_skill_path(path)
    authority_hmac_keys: dict[str, str] = {}
    authority_rsa_keys: dict[str, dict[str, Any]] = {}
    if project_root is not None:
        _, _, _, authority_hmac_keys, authority_rsa_keys = _collect_authority_trust_data(project_root)
    trust_health = load_trust_health(project_root, profile) if project_root is not None else {"revocations": {"revoked_key_ids": [], "present": False, "valid": True, "issues": []}, "transparency_log": {"present": False, "valid": True, "entry_count": 0, "malformed_count": 0, "issues": []}}
    authority_health = trust_health.get("authority", {}) if isinstance(trust_health.get("authority"), dict) else {}
    for key_id, value in authority_hmac_keys.items():
        trusted_keys.setdefault(key_id, value)
    for key_id, value in authority_rsa_keys.items():
        trusted_public_keys.setdefault(key_id, value)
    revoked_key_ids = set(trust_health["revocations"].get("revoked_key_ids", []))
    revoked_key_ids.update(authority_health.get("revoked_key_ids", []))
    manifest_path = path / PUBLISHER_MANIFEST_NAME
    signature_path = path / PUBLISHER_SIGNATURE_NAME
    expected_manifest = _canonical_publisher_manifest(path)
    expected_manifest_bytes = _canonical_json_bytes(expected_manifest)
    expected_manifest_digest = _sha256_bytes(expected_manifest_bytes)

    result = {
        "state": "skipped",
        "valid": True,
        "mode": mode,
        "signature_scheme_mode": signature_scheme_mode,
        "allowed_algorithms": allowed_algorithms,
        "algorithm": PUBLISHER_SIGNATURE_KEY_ALGO,
        "manifest_path": PUBLISHER_MANIFEST_NAME,
        "signature_path": PUBLISHER_SIGNATURE_NAME,
        "message": "publisher verification skipped",
        "expected_manifest_sha256": expected_manifest_digest,
        "trusted_publisher_key_ids": list(trusted_keys.keys()),
        "trusted_publisher_public_key_ids": list(trusted_public_keys.keys()),
        "key_rotation": key_rotation,
        "revocation_status": "clear",
        "revoked_key_ids": sorted(revoked_key_ids),
        "trust_health": trust_health,
    }

    def _finalize(result: dict) -> dict:
        if project_root is not None:
            _append_transparency_log(project_root, result, path)
        return result

    if mode == PUBLISHER_SIGNATURE_MODE_OFF:
        result["message"] = "publisher verification disabled by profile"
        return _finalize(result)

    if not manifest_path.exists() or not signature_path.exists():
        result.update(
            {
                "state": "missing",
                "valid": False,
                "message": f"missing {PUBLISHER_MANIFEST_NAME} or {PUBLISHER_SIGNATURE_NAME}",
            }
        )
        return _finalize(result)

    manifest_payload = _load_json_file(manifest_path)
    signature_payload = _load_json_file(signature_path)
    if manifest_payload is None or signature_payload is None:
        result.update(
            {
                "state": "invalid",
                "valid": False,
                "message": "publisher verification artifact is not valid JSON",
            }
        )
        return _finalize(result)

    manifest_view = {
        "algorithm": str(manifest_payload.get("algorithm", "")).strip().lower() or "sha256",
        "files": manifest_payload.get("files", []),
    }
    if manifest_view != expected_manifest:
        result.update(
            {
                "state": "invalid",
                "valid": False,
                "message": f"{PUBLISHER_MANIFEST_NAME} does not match downloaded skill contents",
            }
        )
        return _finalize(result)

    sig_algorithm = str(signature_payload.get("algorithm", "")).strip().lower()
    key_id = str(signature_payload.get("key_id", "")).strip()
    signature_value = str(signature_payload.get("signature", "")).strip()
    if sig_algorithm not in allowed_algorithms:
        result.update(
            {
                "state": "unsupported",
                "valid": False,
                "message": f"unsupported publisher signature algorithm '{sig_algorithm or 'unknown'}'",
                "key_id": key_id or None,
                "algorithm": sig_algorithm or None,
            }
        )
        return _finalize(result)
    if signature_scheme_mode == PUBLISHER_SIGNATURE_SCHEME_HMAC and sig_algorithm != PUBLISHER_SIGNATURE_KEY_ALGO:
        result.update(
            {
                "state": "unsupported",
                "valid": False,
                "message": "publisher signature algorithm is not allowed when publisher_signature_scheme_mode is hmac",
                "key_id": key_id or None,
                "algorithm": sig_algorithm or None,
            }
        )
        return _finalize(result)
    if signature_scheme_mode == PUBLISHER_SIGNATURE_SCHEME_RSA and sig_algorithm != PUBLISHER_SIGNATURE_RSA_ALGO:
        result.update(
            {
                "state": "unsupported",
                "valid": False,
                "message": "publisher signature algorithm is not allowed when publisher_signature_scheme_mode is rsa",
                "key_id": key_id or None,
                "algorithm": sig_algorithm or None,
            }
        )
        return _finalize(result)
    if not key_id:
        result.update({"state": "invalid", "valid": False, "message": "publisher signature is missing key_id"})
        return _finalize(result)
    if not signature_value:
        result.update({"state": "invalid", "valid": False, "message": "publisher signature is empty", "key_id": key_id})
        return _finalize(result)

    if key_id in revoked_key_ids:
        result.update(
            {
                "state": "revoked",
                "valid": False,
                "message": f"publisher key '{key_id}' is revoked by {PUBLISHER_REVOCATIONS_NAME}",
                "key_id": key_id,
                "algorithm": sig_algorithm,
                "scheme": PUBLISHER_SIGNATURE_SCHEME_HMAC if sig_algorithm == PUBLISHER_SIGNATURE_KEY_ALGO else PUBLISHER_SIGNATURE_SCHEME_RSA,
                "method": "shared-secret" if sig_algorithm == PUBLISHER_SIGNATURE_KEY_ALGO else "public-key",
                "revocation_status": "revoked",
            }
        )
        return _finalize(result)

    if sig_algorithm == PUBLISHER_SIGNATURE_KEY_ALGO:
        if key_id not in trusted_keys:
            result.update(
                {
                    "state": "untrusted",
                    "valid": False,
                    "message": f"publisher key '{key_id}' is not trusted by the current profile",
                    "key_id": key_id,
                    "algorithm": sig_algorithm,
                    "scheme": PUBLISHER_SIGNATURE_SCHEME_HMAC,
                    "method": "shared-secret",
                }
            )
            return _finalize(result)

        expected_signature = hmac.new(
            trusted_keys[key_id].encode("utf-8"), expected_manifest_bytes, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature_value, expected_signature):
            result.update(
                {
                    "state": "invalid",
                    "valid": False,
                    "message": f"publisher signature mismatch for key '{key_id}'",
                    "key_id": key_id,
                    "algorithm": sig_algorithm,
                    "scheme": PUBLISHER_SIGNATURE_SCHEME_HMAC,
                    "method": "shared-secret",
                }
            )
            return _finalize(result)

        result.update(
            {
                "state": "valid",
                "valid": True,
                "message": f"publisher verification valid ({PUBLISHER_SIGNATURE_KEY_ALGO}, key_id={key_id}, method=shared-secret)",
                "key_id": key_id,
                "algorithm": PUBLISHER_SIGNATURE_KEY_ALGO,
                "scheme": PUBLISHER_SIGNATURE_SCHEME_HMAC,
                "method": "shared-secret",
            }
        )
        return _finalize(result)

    if key_id not in trusted_public_keys:
        result.update(
            {
                "state": "untrusted",
                "valid": False,
                "message": f"publisher key '{key_id}' is not trusted by the current profile",
                "key_id": key_id,
                "algorithm": sig_algorithm,
                "scheme": PUBLISHER_SIGNATURE_SCHEME_RSA,
                "method": "public-key",
            }
        )
        return _finalize(result)

    if not _verify_rsa_sha256_signature(signature_value, trusted_public_keys[key_id], expected_manifest_bytes):
        result.update(
            {
                "state": "invalid",
                "valid": False,
                "message": f"publisher signature mismatch for key '{key_id}'",
                "key_id": key_id,
                "algorithm": sig_algorithm,
                "scheme": PUBLISHER_SIGNATURE_SCHEME_RSA,
                "method": "public-key",
            }
        )
        return _finalize(result)

    result.update(
        {
            "state": "valid",
            "valid": True,
            "message": f"publisher verification valid ({PUBLISHER_SIGNATURE_RSA_ALGO}, key_id={key_id}, method=public-key)",
            "key_id": key_id,
            "algorithm": PUBLISHER_SIGNATURE_RSA_ALGO,
            "scheme": PUBLISHER_SIGNATURE_SCHEME_RSA,
            "method": "public-key",
        }
    )
    return _finalize(result)


def _clean_dict(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _normalize_recommendation(candidate: Any) -> dict:
    metadata = candidate.metadata if isinstance(getattr(candidate, "metadata", None), dict) else {}
    raw = metadata.get("recommendation") if isinstance(metadata.get("recommendation"), dict) else {}
    reasons = raw.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        if candidate.source == "local":
            reasons = ["manual install"]
        else:
            reasons = [f"installed from {candidate.source}"]
    score = raw.get("score", metadata.get("recommendation_score", getattr(candidate, "trust_score", 0)))
    try:
        score = int(score)
    except Exception:
        score = int(getattr(candidate, "trust_score", 0))
    return _clean_dict(
        {
            "reasons": [str(reason) for reason in reasons],
            "score": score,
            "reason_hash": raw.get("reason_hash", metadata.get("recommendation_reason_hash", _reason_hash(reasons))),
            "selected_by": raw.get("selected_by", metadata.get("selected_by", "skillsmith")),
            "selection_mode": raw.get("selection_mode", metadata.get("selection_mode", "manual")),
            "query": raw.get("query"),
            "matched_query": raw.get("matched_query"),
            "matched_profile": raw.get("matched_profile"),
            "starter_pack_label": raw.get("starter_pack_label"),
        }
    )


def _normalize_provenance(candidate: Any) -> dict:
    metadata = candidate.metadata if isinstance(getattr(candidate, "metadata", None), dict) else {}
    raw = metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
    verification = raw.get("publisher_verification") if isinstance(raw.get("publisher_verification"), dict) else {}
    install_kind = raw.get("install_kind") or metadata.get("install_kind")
    if not install_kind:
        install_kind = "local-template" if candidate.source == "local" else "remote"
    return _clean_dict(
        {
            "install_kind": install_kind,
            "source": raw.get("source", candidate.source),
            "install_ref": raw.get("install_ref", candidate.install_ref),
            "requested_name": raw.get("requested_name", metadata.get("requested_name")),
            "requested_query": raw.get("requested_query", metadata.get("requested_query")),
            "requested_url": raw.get("requested_url", metadata.get("requested_url")),
            "selected_by": raw.get("selected_by", metadata.get("selected_by", "manual")),
            "source_domain": raw.get("source_domain"),
            "requested_url_sha256": raw.get("requested_url_sha256"),
            "resolved_ref": raw.get("resolved_ref"),
            "resolved_ref_type": raw.get("resolved_ref_type"),
            "pinned_ref": raw.get("pinned_ref"),
            "fetched_at": raw.get("fetched_at"),
            "publisher_verification": raw.get("publisher_verification", metadata.get("publisher_verification")),
            "publisher_verification_method": raw.get(
                "publisher_verification_method",
                metadata.get("publisher_verification_method", verification.get("method")),
            ),
            "publisher_verification_algorithm": raw.get(
                "publisher_verification_algorithm",
                metadata.get("publisher_verification_algorithm", verification.get("algorithm")),
            ),
            "publisher_signature_scheme_mode": raw.get(
                "publisher_signature_scheme_mode",
                metadata.get("publisher_signature_scheme_mode", verification.get("signature_scheme_mode")),
            ),
            "publisher_signature_algorithms": raw.get(
                "publisher_signature_algorithms",
                metadata.get("publisher_signature_algorithms", verification.get("allowed_algorithms")),
            ),
            "publisher_key_rotation": raw.get(
                "publisher_key_rotation", metadata.get("publisher_key_rotation", verification.get("key_rotation"))
            ),
        }
    )


def load_lockfile(cwd: Path) -> dict:
    path = cwd / LOCKFILE_NAME
    if not path.exists():
        return {"version": LOCKFILE_VERSION, "schema_version": LOCKFILE_SCHEMA_VERSION, "skills": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": LOCKFILE_VERSION, "schema_version": LOCKFILE_SCHEMA_VERSION, "skills": []}
    if not isinstance(payload, dict):
        return {"version": LOCKFILE_VERSION, "schema_version": LOCKFILE_SCHEMA_VERSION, "skills": []}
    payload.setdefault("version", LOCKFILE_VERSION)
    payload.setdefault("schema_version", 1)
    payload.setdefault("skills", [])
    return payload


def write_lockfile(cwd: Path, payload: dict) -> None:
    normalized = dict(payload)
    normalized.setdefault("version", LOCKFILE_VERSION)
    normalized["schema_version"] = LOCKFILE_SCHEMA_VERSION
    normalized.setdefault("skills", [])
    signature = sign_lockfile_payload(normalized)
    if signature is not None:
        normalized["signature"] = signature
    else:
        normalized.pop("signature", None)
    target = cwd / LOCKFILE_NAME
    fd, temp_name = tempfile.mkstemp(prefix=f"{LOCKFILE_NAME}.", suffix=".tmp", dir=str(cwd))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(normalized, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def refresh_local_lockfile_verification_timestamps(
    cwd: Path,
    payload: dict,
    *,
    now: datetime.datetime | None = None,
    stale_after_days: int = VERIFICATION_STALE_DAYS,
) -> tuple[dict, list[dict], bool]:
    current_time = now or _utc_now()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=datetime.timezone.utc)
    current_time = current_time.astimezone(datetime.timezone.utc)
    current_time_text = _timestamp_to_string(current_time)
    stale_after = datetime.timedelta(days=stale_after_days)

    updated_payload = dict(payload)
    skills = updated_payload.get("skills", [])
    if not isinstance(skills, list):
        return updated_payload, [], False

    changed = False
    findings: list[dict] = []
    refreshed_skills: list[Any] = []
    for raw_entry in skills:
        entry = dict(raw_entry) if isinstance(raw_entry, dict) else raw_entry
        finding = {
            "name": "unknown",
            "source": "unknown",
            "state": "skipped",
            "updated": False,
            "previous_verification_timestamp": None,
        }
        if isinstance(entry, dict):
            finding["name"] = str(entry.get("name", "unknown"))
            finding["source"] = str(entry.get("source", "unknown"))

            if finding["source"] == "local":
                path_value = entry.get("path")
                install_path = cwd / path_value if isinstance(path_value, str) and path_value else None
                if install_path is not None and install_path.exists():
                    checksum = str(entry.get("checksum", ""))
                    if _checksum_matches(install_path, checksum):
                        verification_timestamp = _parse_timestamp(entry.get("verification_timestamp"))
                        if verification_timestamp is None:
                            entry["verification_timestamp"] = current_time_text
                            finding["state"] = "unverified"
                            finding["updated"] = True
                            changed = True
                        elif current_time - verification_timestamp >= stale_after:
                            finding["state"] = "stale"
                            finding["updated"] = True
                            finding["previous_verification_timestamp"] = entry.get("verification_timestamp")
                            entry["verification_timestamp"] = current_time_text
                            changed = True
                        else:
                            finding["state"] = "verified"
                    else:
                        finding["state"] = "checksum-mismatch"
                else:
                    finding["state"] = "missing-path"

                if finding["state"] == "unverified":
                    finding["summary"] = "checksum verified but verification timestamp was missing; refreshed"
                elif finding["state"] == "stale":
                    finding["summary"] = "checksum verified but verification timestamp was stale; refreshed"
                elif finding["state"] == "verified":
                    finding["summary"] = "checksum verified"
                elif finding["state"] == "checksum-mismatch":
                    finding["summary"] = "checksum mismatch"
                elif finding["state"] == "missing-path":
                    finding["summary"] = "install path missing"
            else:
                finding["state"] = "skipped"
                finding["summary"] = "not a local skill"
        refreshed_skills.append(entry)
        findings.append(finding)

    if changed:
        updated_payload["skills"] = refreshed_skills

    return updated_payload, findings, changed


def record_skill_install(cwd: Path, candidate: Any, installed_path: Path) -> None:
    payload = load_lockfile(cwd)
    skills = payload.setdefault("skills", [])
    rel_path = installed_path.relative_to(cwd).as_posix()
    entry = {
        "name": candidate.name,
        "source": candidate.source,
        "version": candidate.version,
        "install_ref": candidate.install_ref,
        "trust_score": candidate.trust_score,
        "category": candidate.category,
        "tags": candidate.tags,
        "installed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "verification_timestamp": _timestamp_to_string(),
        "path": rel_path,
        "checksum": _checksum_for_path(installed_path),
        "metadata": candidate.metadata,
        "provenance": _normalize_provenance(candidate),
        "recommendation": _normalize_recommendation(candidate),
    }

    replaced = False
    for index, current in enumerate(skills):
        if current.get("name") == candidate.name and current.get("source") == candidate.source:
            skills[index] = entry
            replaced = True
            break

    if not replaced:
        skills.append(entry)

    write_lockfile(cwd, payload)
