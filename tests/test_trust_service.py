from __future__ import annotations

import json
import hashlib
import hmac
import shutil
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
import uuid
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from skillsmith.commands.trust_service import start_trust_service, sync_trust_authority_files, sync_trust_snapshot


class TrustServiceTests(unittest.TestCase):
    _temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"

    def _request_json(self, base_url: str, method: str, path: str, *, token: str | None = None, body: dict | None = None):
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
        self.fail("trust service did not become ready")

    def _authority_signature(self, payload: dict, secret: str) -> tuple[str, str]:
        canonical = json.dumps(
            {key: value for key, value in payload.items() if key != "signature"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        signature = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest, signature

    @contextmanager
    def _service(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        server, thread, base_url = start_trust_service(cwd, token="trust-token")
        self._wait_for_health(base_url)
        try:
            yield cwd, base_url
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

    def test_trust_service_handles_publish_rotate_revoke_and_history(self):
        with self._service() as (cwd, base_url), mock.patch(
            "skillsmith.commands.trust_service._timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            unauthorized_status, unauthorized_payload = self._request_json(base_url, "GET", "/v1/trust")
            self.assertEqual(unauthorized_status, 401)
            self.assertEqual(unauthorized_payload["error"], "unauthorized")

            publish_status, publish_payload = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token="trust-token",
                body={
                    "key_id": "publisher-primary",
                    "algorithm": "hmac-sha256",
                    "kind": "shared-secret",
                    "material": "secret-123",
                    "actor": "operator-a",
                    "note": "initial publish",
                },
            )
            self.assertEqual(publish_status, 200)
            self.assertEqual(publish_payload["key"]["status"], "active")
            self.assertEqual(publish_payload["key"]["material"], "secret-123")

            rotate_status, rotate_payload = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/rotate",
                token="trust-token",
                body={
                    "current_key_id": "publisher-primary",
                    "key_id": "publisher-next",
                    "algorithm": "hmac-sha256",
                    "kind": "shared-secret",
                    "material": "secret-456",
                    "actor": "operator-a",
                    "note": "scheduled rotation",
                },
            )
            self.assertEqual(rotate_status, 200)
            self.assertEqual(rotate_payload["key"]["key_id"], "publisher-next")
            self.assertEqual(rotate_payload["key"]["previous_key_id"], "publisher-primary")
            self.assertEqual(rotate_payload["key"]["status"], "active")

            revoke_status, revoke_payload = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/revoke",
                token="trust-token",
                body={"key_id": "publisher-next", "reason": "retired", "actor": "operator-a"},
            )
            self.assertEqual(revoke_status, 200)
            self.assertEqual(revoke_payload["key"]["status"], "revoked")
            self.assertEqual(revoke_payload["key"]["revocation_reason"], "retired")

            keys_status, keys_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/tenants/acme/teams/platform/keys",
                token="trust-token",
            )
            self.assertEqual(keys_status, 200)
            self.assertEqual(len(keys_payload["keys"]), 2)
            self.assertEqual(
                {item["key_id"]: item["status"] for item in keys_payload["keys"]},
                {"publisher-primary": "rotated", "publisher-next": "revoked"},
            )

            history_status, history_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/tenants/acme/teams/platform/keys/publisher-next/history",
                token="trust-token",
            )
            self.assertEqual(history_status, 200)
            self.assertEqual([event["action"] for event in history_payload["history"]], ["rotate-to", "revoke"])

            revocations_status, revocations_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/tenants/acme/teams/platform/revocations",
                token="trust-token",
            )
            self.assertEqual(revocations_status, 200)
            self.assertEqual(len(revocations_payload["revocations"]), 1)
            self.assertEqual(revocations_payload["revocations"][0]["key_id"], "publisher-next")

            persisted = json.loads((cwd / ".agent" / "service" / "trust.json").read_text(encoding="utf-8"))
            self.assertEqual(len(persisted["keys"]), 2)
            self.assertEqual(persisted["revocations"][0]["reason"], "retired")

    def test_trust_service_exposes_signed_authority_bootstrap_bundle_and_revocations(self):
        with self._service() as (_, base_url), mock.patch(
            "skillsmith.commands.trust_service._timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token="trust-token",
                body={
                    "key_id": "publisher-primary",
                    "algorithm": "hmac-sha256",
                    "kind": "shared-secret",
                    "material": "secret-123",
                    "actor": "operator-a",
                },
            )
            self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/revoke",
                token="trust-token",
                body={"key_id": "publisher-primary", "reason": "retired", "actor": "operator-a"},
            )

            bootstrap_status, bootstrap_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/authority/bootstrap",
                token="trust-token",
            )
            self.assertEqual(bootstrap_status, 200)
            self.assertEqual(bootstrap_payload["service"], "trust-authority")
            self.assertGreaterEqual(len(bootstrap_payload["trust_roots"]), 1)
            root = bootstrap_payload["trust_roots"][0]
            self.assertEqual(root["algorithm"], "hmac-sha256")
            self.assertIn("secret", root)

            bundle_status, bundle_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/authority/tenants/acme/teams/platform/bundle",
                token="trust-token",
            )
            self.assertEqual(bundle_status, 200)
            self.assertEqual(bundle_payload["tenant_id"], "acme")
            self.assertEqual(bundle_payload["team_id"], "platform")
            self.assertEqual(bundle_payload["keys"][0]["key_id"], "publisher-primary")
            self.assertEqual(bundle_payload["signature"]["algorithm"], "hmac-sha256")
            self.assertEqual(bundle_payload["signature"]["key_id"], root["key_id"])
            digest, signature = self._authority_signature(bundle_payload, root["secret"])
            self.assertEqual(bundle_payload["signature"]["digest"], digest)
            self.assertEqual(bundle_payload["signature"]["signature"], signature)

            revocations_status, revocations_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/authority/tenants/acme/teams/platform/revocations",
                token="trust-token",
            )
            self.assertEqual(revocations_status, 200)
            self.assertEqual(revocations_payload["revocations"][0]["key_id"], "publisher-primary")
            self.assertEqual(revocations_payload["signature"]["algorithm"], "hmac-sha256")
            self.assertEqual(revocations_payload["signature"]["key_id"], root["key_id"])
            digest, signature = self._authority_signature(revocations_payload, root["secret"])
            self.assertEqual(revocations_payload["signature"]["digest"], digest)
            self.assertEqual(revocations_payload["signature"]["signature"], signature)

    def test_trust_sync_helper_writes_local_snapshot(self):
        with self._service() as (cwd, base_url), mock.patch(
            "skillsmith.commands.trust_service._timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token="trust-token",
                body={"key_id": "publisher-primary", "material": "secret-123"},
            )
            target = cwd / "local" / "trust-snapshot.json"
            synced_path = sync_trust_snapshot(base_url, target, token="trust-token")

            self.assertEqual(synced_path, target)
            synced_payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(synced_payload["service"], "trust")
            self.assertEqual(synced_payload["keys"][0]["key_id"], "publisher-primary")
            self.assertEqual(synced_payload["keys"][0]["material"], "secret-123")

    def test_trust_sync_helper_writes_authority_files(self):
        with self._service() as (cwd, base_url), mock.patch(
            "skillsmith.commands.trust_service._timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token="trust-token",
                body={"key_id": "publisher-primary", "material": "secret-123"},
            )
            self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/revoke",
                token="trust-token",
                body={"key_id": "publisher-primary", "reason": "retired"},
            )

            destination = cwd / ".agent" / "trust" / "authority"
            paths = sync_trust_authority_files(
                base_url,
                destination,
                bearer_token="trust-token",
                tenant_id="acme",
                team_id="platform",
            )

            self.assertTrue(paths["bootstrap"].exists())
            self.assertTrue(paths["bundle"].exists())
            self.assertTrue(paths["revocations"].exists())
            bootstrap_payload = json.loads(paths["bootstrap"].read_text(encoding="utf-8"))
            bundle_payload = json.loads(paths["bundle"].read_text(encoding="utf-8"))
            revocations_payload = json.loads(paths["revocations"].read_text(encoding="utf-8"))
            self.assertEqual(bootstrap_payload["service"], "trust-authority")
            self.assertEqual(bundle_payload["keys"][0]["key_id"], "publisher-primary")
            self.assertEqual(revocations_payload["revocations"][0]["key_id"], "publisher-primary")


if __name__ == "__main__":
    unittest.main()
