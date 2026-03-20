from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import shutil
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
import sys
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_REGISTRY_SERVICE_PATH = Path(__file__).resolve().parents[1] / "src" / "skillsmith" / "commands" / "registry_service.py"
_REGISTRY_SERVICE_SPEC = importlib.util.spec_from_file_location("registry_service_under_test", _REGISTRY_SERVICE_PATH)
if _REGISTRY_SERVICE_SPEC is None or _REGISTRY_SERVICE_SPEC.loader is None:
    raise RuntimeError("failed to load registry_service module for tests")
_REGISTRY_SERVICE_MODULE = importlib.util.module_from_spec(_REGISTRY_SERVICE_SPEC)
sys.modules[_REGISTRY_SERVICE_SPEC.name] = _REGISTRY_SERVICE_MODULE
_REGISTRY_SERVICE_SPEC.loader.exec_module(_REGISTRY_SERVICE_MODULE)
start_registry_service = _REGISTRY_SERVICE_MODULE.start_registry_service
sync_registry_snapshot = _REGISTRY_SERVICE_MODULE.sync_registry_snapshot


class RegistryServiceTests(unittest.TestCase):
    _temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"

    def _request_json(
        self,
        base_url: str,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict | None = None,
    ):
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            payload = exc.read().decode("utf-8")
            return exc.code, json.loads(payload)

    def _wait_for_health(self, base_url: str) -> None:
        for _ in range(50):
            try:
                status, _ = self._request_json(base_url, "GET", "/health")
                if status == 200:
                    return
            except Exception:
                pass
            time.sleep(0.02)
        self.fail("registry service did not become ready")

    @contextmanager
    def _service(
        self,
        *,
        token: str = "registry-token",
        authz_policy: dict | None = None,
        oidc_config: dict | None = None,
        backend: str = "json",
        db_file: Path | None = None,
        cwd: Path | None = None,
        cleanup: bool = True,
    ):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"registry-service-{uuid.uuid4().hex}" if cwd is None else Path(cwd)
        cwd.mkdir(parents=True, exist_ok=True)
        authz_file = None
        if authz_policy is not None:
            authz_file = cwd / ".agent" / "service" / "registry-authz.json"
            authz_file.parent.mkdir(parents=True, exist_ok=True)
            authz_file.write_text(json.dumps(authz_policy, indent=2, sort_keys=True), encoding="utf-8")
        oidc_file = None
        if oidc_config is not None:
            oidc_file = cwd / ".agent" / "service" / "registry-oidc.json"
            oidc_file.parent.mkdir(parents=True, exist_ok=True)
            oidc_file.write_text(json.dumps(oidc_config, indent=2, sort_keys=True), encoding="utf-8")
        server, thread, base_url = start_registry_service(
            cwd,
            token=token,
            authz_file=authz_file,
            oidc_config=oidc_file,
            backend=backend,
            db_file=db_file,
        )
        self._wait_for_health(base_url)
        try:
            yield cwd, base_url
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            if cleanup:
                shutil.rmtree(cwd, ignore_errors=True)

    def _jwt(self, payload: dict, *, secret: str, header: dict | None = None) -> str:
        token_header = {"alg": "HS256", "typ": "JWT"}
        if header:
            token_header.update(header)

        def encode(part: dict) -> str:
            raw = json.dumps(part, sort_keys=True, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

        encoded_header = encode(token_header)
        encoded_payload = encode(payload)
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def _oidc_config(self) -> dict:
        return {
            "issuer": "https://issuer.example",
            "audience": "skillsmith-registry",
            "shared_secret": "dev-secret",
            "algorithms": ["HS256"],
            "claims": {
                "subject": "sub",
                "name": "email",
                "roles": "roles",
                "groups": "groups",
                "tenants": "tenants",
                "teams": "teams",
            },
            "group_role_map": {"registry-approvers": ["approver"]},
            "default_roles": ["viewer"],
        }

    def test_registry_service_tracks_approvals_history_and_auth(self):
        with self._service() as (cwd, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            unauthorized_status, unauthorized_payload = self._request_json(base_url, "GET", "/v1/registry")
            self.assertEqual(unauthorized_status, 401)
            self.assertEqual(unauthorized_payload["error"], "unauthorized")

            create_status, create_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="registry-token",
                body={
                    "entry_id": "alpha-skill",
                    "name": "Alpha Skill",
                    "description": "Registry entry for alpha",
                    "state": "draft",
                    "approval_state": "not_requested",
                    "source": "manual",
                    "owners": ["team-a", "team-b"],
                    "tags": ["governance", "platform"],
                    "notes": "initial draft",
                    "actor": "creator",
                },
            )
            self.assertEqual(create_status, 200)
            self.assertEqual(create_payload["entry"]["entry_id"], "alpha-skill")
            self.assertEqual(create_payload["entry"]["tenant_id"], "acme")
            self.assertEqual(create_payload["entry"]["team_id"], "platform")

            request_status, request_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/alpha-skill/approvals",
                token="registry-token",
                body={"decision": "approved", "actor": "reviewer-a", "note": "ready for review"},
            )
            self.assertEqual(request_status, 200)
            self.assertEqual(request_payload["entry"]["approval_status"], "approved")
            self.assertEqual(request_payload["entry"]["lifecycle_state"], "approved")

            history_status, history_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/alpha-skill/history",
                token="registry-token",
                body={"action": "audit", "actor": "auditor", "note": "spot check"},
            )
            self.assertEqual(history_status, 200)
            self.assertEqual(history_payload["entry"]["change_history"][-1]["action"], "audit")

            approvals_status, approvals_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/approvals",
                token="registry-token",
            )
            self.assertEqual(approvals_status, 200)
            self.assertEqual(len(approvals_payload["approvals"]), 1)
            self.assertEqual(approvals_payload["approvals"][0]["entry_id"], "alpha-skill")

            entry_status, entry_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/entries/alpha-skill",
                token="registry-token",
            )
            self.assertEqual(entry_status, 200)
            self.assertEqual([event["action"] for event in entry_payload["change_history"]], ["create", "approved", "audit"])
            self.assertEqual([approval["decision"] for approval in entry_payload["approvals"]], ["approved"])

            persisted = json.loads((cwd / ".agent" / "service" / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["entries"][0]["entry_id"], "alpha-skill")
            self.assertEqual(persisted["entries"][0]["approvals"][0]["actor"], "reviewer-a")

    def test_registry_service_sqlite_backend_persists_state_across_restart(self):
        db_file = Path(".agent/service/registry.sqlite3")
        with self._service(backend="sqlite", db_file=db_file, cleanup=False) as (cwd, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, create_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="registry-token",
                body={
                    "entry_id": "sqlite-skill",
                    "name": "SQLite Skill",
                    "description": "Persisted in sqlite",
                    "actor": "creator",
                },
            )
            self.assertEqual(create_status, 200)
            self.assertEqual(create_payload["entry"]["entry_id"], "sqlite-skill")

        with self._service(backend="sqlite", db_file=db_file, cwd=cwd) as (_, base_url):
            entry_status, entry_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/entries/sqlite-skill",
                token="registry-token",
            )
            self.assertEqual(entry_status, 200)
            self.assertEqual(entry_payload["entry_id"], "sqlite-skill")
            self.assertEqual(entry_payload["name"], "SQLite Skill")

    def test_registry_service_sqlite_backend_imports_legacy_json_once(self):
        db_file = Path(".agent/service/registry.sqlite3")
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"registry-service-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        legacy_path = cwd / ".agent" / "service" / "registry.json"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps(
                {
                    "service": "registry",
                    "version": 1,
                    "generated_at": "2026-03-19T12:00:00Z",
                    "entries": [
                        {
                            "tenant_id": "acme",
                            "team_id": "platform",
                            "entry_id": "legacy-skill",
                            "name": "Legacy Skill",
                            "description": "Imported from legacy json",
                            "source": "manual",
                            "lifecycle_state": "draft",
                            "approval_status": "not_requested",
                            "owners": ["team-a"],
                            "tags": ["legacy"],
                            "approvals": [],
                            "change_history": [],
                            "created_at": "2026-03-19T12:00:00Z",
                            "updated_at": "2026-03-19T12:00:00Z",
                        }
                    ],
                    "skills": [],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        server, thread, base_url = start_registry_service(cwd, token="registry-token", backend="sqlite", db_file=db_file)
        self._wait_for_health(base_url)
        try:
            entry_status, entry_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/entries/legacy-skill",
                token="registry-token",
            )
            self.assertEqual(entry_status, 200)
            self.assertEqual(entry_payload["entry_id"], "legacy-skill")
            self.assertEqual(entry_payload["description"], "Imported from legacy json")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        legacy_path.write_text(
            json.dumps(
                {
                    "service": "registry",
                    "version": 1,
                    "generated_at": "2026-03-19T13:00:00Z",
                    "entries": [
                        {
                            "tenant_id": "acme",
                            "team_id": "platform",
                            "entry_id": "different-skill",
                            "name": "Different Skill",
                            "description": "Should not be reimported",
                            "source": "manual",
                            "lifecycle_state": "draft",
                            "approval_status": "not_requested",
                            "owners": [],
                            "tags": [],
                            "approvals": [],
                            "change_history": [],
                            "created_at": "2026-03-19T13:00:00Z",
                            "updated_at": "2026-03-19T13:00:00Z",
                        }
                    ],
                    "skills": [],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        with self._service(backend="sqlite", db_file=db_file, cwd=cwd) as (_, base_url):
            entry_status, entry_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/entries/legacy-skill",
                token="registry-token",
            )
            self.assertEqual(entry_status, 200)
            self.assertEqual(entry_payload["entry_id"], "legacy-skill")
            missing_status, missing_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/platform/entries/different-skill",
                token="registry-token",
            )
            self.assertEqual(missing_status, 404)
            self.assertEqual(missing_payload["error"], "entry not found")

    def test_registry_service_serve_command_forwards_sqlite_backend_options(self):
        with mock.patch.object(_REGISTRY_SERVICE_MODULE, "run_registry_service") as run_service:
            from click.testing import CliRunner

            result = CliRunner().invoke(
                _REGISTRY_SERVICE_MODULE.registry_service_command,
                [
                    "serve",
                    "--backend",
                    "sqlite",
                    "--db-file",
                    "custom-registry.sqlite3",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            run_service.assert_called_once()
            args, kwargs = run_service.call_args
            self.assertEqual(kwargs["backend"], "sqlite")
            self.assertEqual(kwargs["db_file"], Path("custom-registry.sqlite3"))
            self.assertEqual(kwargs["host"], "127.0.0.1")

    def test_registry_service_oidc_token_allows_scoped_access_and_reports_whoami(self):
        config = self._oidc_config()
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        token = self._jwt(
            {
                "iss": config["issuer"],
                "aud": config["audience"],
                "exp": exp,
                "sub": "user-123",
                "email": "user@example.com",
                "roles": ["editor"],
                "tenants": ["acme"],
                "teams": {"acme": ["platform"]},
            },
            secret=config["shared_secret"],
        )
        with self._service(oidc_config=config) as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, create_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token=token,
                body={"entry_id": "oidc-skill", "name": "OIDC Skill", "description": "OIDC-backed create"},
            )
            self.assertEqual(create_status, 200)
            self.assertEqual(create_payload["entry"]["entry_id"], "oidc-skill")

            forbidden_status, forbidden_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/acme/teams/other/entries/oidc-skill",
                token=token,
            )
            self.assertEqual(forbidden_status, 403)
            self.assertEqual(forbidden_payload["error"], "forbidden")

            whoami_status, whoami_payload = self._request_json(base_url, "GET", "/v1/whoami", token=token)
            self.assertEqual(whoami_status, 200)
            self.assertEqual(whoami_payload["auth"]["mode"], "oidc")
            self.assertEqual(whoami_payload["auth"]["name"], "user@example.com")
            self.assertEqual(whoami_payload["auth"]["roles"], ["viewer", "editor"])

    def test_registry_service_oidc_rejects_invalid_issuer_audience_and_signature(self):
        config = self._oidc_config()
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        with self._service(oidc_config=config) as (_, base_url):
            invalid_issuer = self._jwt(
                {
                    "iss": "https://bad-issuer.example",
                    "aud": config["audience"],
                    "exp": exp,
                    "sub": "user-123",
                    "roles": ["viewer"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
                secret=config["shared_secret"],
            )
            issuer_status, issuer_payload = self._request_json(base_url, "GET", "/v1/registry", token=invalid_issuer)
            self.assertEqual(issuer_status, 401)
            self.assertEqual(issuer_payload["error"], "unauthorized")

            invalid_audience = self._jwt(
                {
                    "iss": config["issuer"],
                    "aud": "wrong-audience",
                    "exp": exp,
                    "sub": "user-123",
                    "roles": ["viewer"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
                secret=config["shared_secret"],
            )
            audience_status, audience_payload = self._request_json(base_url, "GET", "/v1/registry", token=invalid_audience)
            self.assertEqual(audience_status, 401)
            self.assertEqual(audience_payload["error"], "unauthorized")

            invalid_signature = self._jwt(
                {
                    "iss": config["issuer"],
                    "aud": config["audience"],
                    "exp": exp,
                    "sub": "user-123",
                    "roles": ["viewer"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
                secret="wrong-secret",
            )
            signature_status, signature_payload = self._request_json(base_url, "GET", "/v1/registry", token=invalid_signature)
            self.assertEqual(signature_status, 401)
            self.assertEqual(signature_payload["error"], "unauthorized")

    def test_registry_service_oidc_group_role_mapping_allows_approval(self):
        config = self._oidc_config()
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        admin_token = self._jwt(
            {
                "iss": config["issuer"],
                "aud": config["audience"],
                "exp": exp,
                "sub": "admin-1",
                "email": "admin@example.com",
                "roles": ["admin"],
                "tenants": ["*"],
                "teams": {"*": ["*"]},
            },
            secret=config["shared_secret"],
        )
        approver_token = self._jwt(
            {
                "iss": config["issuer"],
                "aud": config["audience"],
                "exp": exp,
                "sub": "approver-1",
                "email": "approver@example.com",
                "groups": ["registry-approvers"],
                "tenants": ["acme"],
                "teams": {"acme": ["platform"]},
            },
            secret=config["shared_secret"],
        )
        with self._service(oidc_config=config) as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token=admin_token,
                body={"entry_id": "approval-skill", "name": "Approval Skill", "description": "Awaiting approval"},
            )
            self.assertEqual(create_status, 200)

            approval_status, approval_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/approval-skill/approvals",
                token=approver_token,
                body={"decision": "approved", "actor": "approver"},
            )
            self.assertEqual(approval_status, 200)
            self.assertEqual(approval_payload["entry"]["approval_status"], "approved")

    def test_registry_service_serve_command_forwards_oidc_config(self):
        with mock.patch.object(_REGISTRY_SERVICE_MODULE, "run_registry_service") as run_service:
            from click.testing import CliRunner

            result = CliRunner().invoke(
                _REGISTRY_SERVICE_MODULE.registry_service_command,
                [
                    "serve",
                    "--oidc-config",
                    "registry-oidc.json",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            _, kwargs = run_service.call_args
            self.assertEqual(kwargs["oidc_config"], Path("registry-oidc.json"))

    def test_registry_service_legacy_token_mode_still_allows_full_access(self):
        with self._service() as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, create_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/beta/teams/platform/entries",
                token="registry-token",
                body={
                    "entry_id": "beta-skill",
                    "name": "Beta Skill",
                    "description": "Registry entry for beta",
                    "actor": "legacy-creator",
                },
            )
            self.assertEqual(create_status, 200)
            self.assertEqual(create_payload["entry"]["tenant_id"], "beta")

            get_status, get_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/beta/teams/platform/entries/beta-skill",
                token="registry-token",
            )
            self.assertEqual(get_status, 200)
            self.assertEqual(get_payload["entry_id"], "beta-skill")

    def test_registry_service_denies_cross_tenant_access_with_authz_policy(self):
        policy = {
            "tokens": {
                "admin-token": {
                    "roles": ["admin"],
                    "tenants": ["*"],
                    "teams": {"*": ["*"]},
                },
                "tenant-a-token": {
                    "roles": ["viewer"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
            }
        }
        with self._service(authz_policy=policy) as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/beta/teams/platform/entries",
                token="admin-token",
                body={
                    "entry_id": "beta-skill",
                    "name": "Beta Skill",
                    "description": "Registry entry for beta",
                },
            )
            self.assertEqual(create_status, 200)

            forbidden_status, forbidden_payload = self._request_json(
                base_url,
                "GET",
                "/v1/registry/tenants/beta/teams/platform/entries/beta-skill",
                token="tenant-a-token",
            )
            self.assertEqual(forbidden_status, 403)
            self.assertEqual(forbidden_payload["error"], "forbidden")

    def test_registry_service_denies_editor_approval_without_approver_role(self):
        policy = {
            "tokens": {
                "admin-token": {
                    "roles": ["admin"],
                    "tenants": ["*"],
                    "teams": {"*": ["*"]},
                },
                "editor-token": {
                    "roles": ["viewer", "editor"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
            }
        }
        with self._service(authz_policy=policy) as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            create_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="admin-token",
                body={
                    "entry_id": "alpha-skill",
                    "name": "Alpha Skill",
                    "description": "Registry entry for alpha",
                },
            )
            self.assertEqual(create_status, 200)

            forbidden_status, forbidden_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/alpha-skill/approvals",
                token="editor-token",
                body={"decision": "approved", "actor": "editor"},
            )
            self.assertEqual(forbidden_status, 403)
            self.assertEqual(forbidden_payload["error"], "forbidden")

    def test_registry_service_allows_approver_and_admin_approval_decisions(self):
        policy = {
            "tokens": {
                "admin-token": {
                    "roles": ["admin"],
                    "tenants": ["*"],
                    "teams": {"*": ["*"]},
                },
                "approver-token": {
                    "roles": ["viewer", "approver"],
                    "tenants": ["acme"],
                    "teams": {"acme": ["platform"]},
                },
            }
        }
        with self._service(authz_policy=policy) as (_, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            first_create_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="admin-token",
                body={
                    "entry_id": "alpha-skill",
                    "name": "Alpha Skill",
                    "description": "Registry entry for alpha",
                },
            )
            self.assertEqual(first_create_status, 200)

            approver_status, approver_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/alpha-skill/approvals",
                token="approver-token",
                body={"decision": "approved", "actor": "approver"},
            )
            self.assertEqual(approver_status, 200)
            self.assertEqual(approver_payload["entry"]["approval_status"], "approved")
            self.assertEqual(approver_payload["entry"]["lifecycle_state"], "approved")

            second_create_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="admin-token",
                body={
                    "entry_id": "beta-skill",
                    "name": "Beta Skill",
                    "description": "Registry entry for beta",
                },
            )
            self.assertEqual(second_create_status, 200)

            admin_status, admin_payload = self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries/beta-skill/approvals",
                token="admin-token",
                body={"decision": "withdrawn", "actor": "admin"},
            )
            self.assertEqual(admin_status, 200)
            self.assertEqual(admin_payload["entry"]["approval_status"], "withdrawn")

    def test_registry_sync_helper_writes_local_snapshot(self):
        with self._service() as (cwd, base_url), mock.patch.object(
            _REGISTRY_SERVICE_MODULE,
            "_timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            self._request_json(
                base_url,
                "POST",
                "/v1/registry/tenants/acme/teams/platform/entries",
                token="registry-token",
                body={"entry_id": "beta-skill", "name": "Beta Skill", "description": "beta"},
            )
            target = cwd / "local" / "registry-snapshot.json"
            synced_path = sync_registry_snapshot(base_url, target, token="registry-token")

            self.assertEqual(synced_path, target)
            synced_payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(synced_payload["service"], "registry")
            self.assertEqual(synced_payload["entries"][0]["entry_id"], "beta-skill")
            self.assertEqual(synced_payload["skills"][0]["entry_id"], "beta-skill")


if __name__ == "__main__":
    unittest.main()
