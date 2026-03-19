from __future__ import annotations

import importlib.util
import json
import shutil
import time
import unittest
from contextlib import contextmanager
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
    def _service(self, *, token: str = "registry-token", authz_policy: dict | None = None):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"registry-service-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        authz_file = None
        if authz_policy is not None:
            authz_file = cwd / ".agent" / "service" / "registry-authz.json"
            authz_file.parent.mkdir(parents=True, exist_ok=True)
            authz_file.write_text(json.dumps(authz_policy, indent=2, sort_keys=True), encoding="utf-8")
        server, thread, base_url = start_registry_service(cwd, token=token, authz_file=authz_file)
        self._wait_for_health(base_url)
        try:
            yield cwd, base_url
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

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
