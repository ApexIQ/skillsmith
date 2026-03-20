from __future__ import annotations

import base64
import json
import hashlib
import hmac
import shutil
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
import sqlite3
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

    def _base64url_encode(self, payload: bytes) -> str:
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    def _jwt_token(
        self,
        secret: str,
        *,
        issuer: str = "https://issuer.example",
        audience: str = "skillsmith-trust",
        claims: dict | None = None,
    ) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": issuer,
            "aud": audience,
            "sub": "user-1",
            "email": "user@example.com",
            "roles": ["viewer"],
            "tenants": ["acme"],
            "teams": {"acme": ["platform"]},
            "exp": 4102444800,
        }
        if claims:
            payload.update(claims)
        encoded_header = self._base64url_encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        encoded_payload = self._base64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        encoded_signature = self._base64url_encode(signature)
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def _read_sqlite_state(self, path: Path) -> dict:
        with sqlite3.connect(path, timeout=2.0) as connection:
            row = connection.execute("SELECT payload FROM service_state WHERE id = 1").fetchone()
        if row is None:
            raise AssertionError(f"sqlite state missing at {path}")
        payload = json.loads(row[0])
        if not isinstance(payload, dict):
            raise AssertionError(f"sqlite state at {path} was not a JSON object")
        return payload

    def _start_service(
        self,
        cwd: Path,
        *,
        backend: str = "json",
        db_file: Path | None = None,
        authority_db_file: Path | None = None,
        oidc_config: Path | None = None,
        signer_provider: str = "local-hmac",
    ):
        server, thread, base_url = start_trust_service(
            cwd,
            token="trust-token",
            backend=backend,
            db_file=db_file,
            authority_db_file=authority_db_file,
            oidc_config=oidc_config,
            signer_provider=signer_provider,
        )
        self._wait_for_health(base_url)
        return server, thread, base_url

    @contextmanager
    def _service(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        server, thread, base_url = self._start_service(cwd)
        try:
            yield cwd, base_url
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

    def _write_legacy_trust_json(self, cwd: Path, payload: dict) -> Path:
        path = cwd / ".agent" / "service" / "trust.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _write_legacy_authority_json(self, cwd: Path, payload: dict) -> Path:
        path = cwd / ".agent" / "service" / "trust-authority.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _write_oidc_config(self, cwd: Path, payload: dict) -> Path:
        path = cwd / ".agent" / "service" / "trust-oidc.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

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

    def test_trust_service_oidc_allows_scoped_read_and_write(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-oidc-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        oidc_path = self._write_oidc_config(
            cwd,
            {
                "issuer": "https://issuer.example",
                "audience": "skillsmith-trust",
                "shared_secret": "oidc-secret",
                "algorithms": ["HS256"],
                "claims": {
                    "subject": "sub",
                    "name": "email",
                    "roles": "roles",
                    "groups": "groups",
                    "tenants": "tenants",
                    "teams": "teams",
                },
            },
        )
        server, thread, base_url = self._start_service(cwd, oidc_config=oidc_path)
        try:
            editor_token = self._jwt_token(
                "oidc-secret",
                claims={"roles": ["editor"], "tenants": ["acme"], "teams": {"acme": ["platform"]}},
            )
            viewer_token = self._jwt_token(
                "oidc-secret",
                claims={"roles": ["viewer"], "tenants": ["acme"], "teams": {"acme": ["platform"]}},
            )
            other_team_token = self._jwt_token(
                "oidc-secret",
                claims={"roles": ["viewer"], "tenants": ["acme"], "teams": {"acme": ["ops"]}},
            )

            publish_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token=editor_token,
                body={"key_id": "oidc-key", "material": "secret-123", "actor": "oidc-user"},
            )
            self.assertEqual(publish_status, 200)

            read_status, read_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/tenants/acme/teams/platform/keys",
                token=viewer_token,
            )
            self.assertEqual(read_status, 200)
            self.assertEqual(read_payload["keys"][0]["key_id"], "oidc-key")

            forbidden_write_status, forbidden_write_payload = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token=viewer_token,
                body={"key_id": "viewer-write", "material": "secret-456", "actor": "viewer"},
            )
            self.assertEqual(forbidden_write_status, 403)
            self.assertEqual(forbidden_write_payload["error"], "forbidden")

            forbidden_scope_status, forbidden_scope_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/tenants/acme/teams/platform/keys",
                token=other_team_token,
            )
            self.assertEqual(forbidden_scope_status, 403)
            self.assertEqual(forbidden_scope_payload["error"], "forbidden")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

    def test_trust_service_oidc_rejects_invalid_issuer_audience_and_signature(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-oidc-invalid-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        oidc_path = self._write_oidc_config(
            cwd,
            {
                "issuer": "https://issuer.example",
                "audience": "skillsmith-trust",
                "shared_secret": "oidc-secret",
            },
        )
        server, thread, base_url = self._start_service(cwd, oidc_config=oidc_path)
        try:
            bad_issuer = self._jwt_token("oidc-secret", issuer="https://wrong.example")
            bad_audience = self._jwt_token("oidc-secret", audience="wrong-audience")
            bad_signature = self._jwt_token("wrong-secret")

            for token in (bad_issuer, bad_audience, bad_signature):
                status, payload = self._request_json(base_url, "GET", "/v1/trust", token=token)
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"], "unauthorized")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

    def test_trust_service_external_signer_returns_clear_error(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-external-signer-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        server, thread, base_url = self._start_service(cwd, signer_provider="external")
        try:
            publish_status, _ = self._request_json(
                base_url,
                "POST",
                "/v1/trust/tenants/acme/teams/platform/keys/publish",
                token="trust-token",
                body={"key_id": "publisher-primary", "material": "secret-123"},
            )
            self.assertEqual(publish_status, 200)

            bundle_status, bundle_payload = self._request_json(
                base_url,
                "GET",
                "/v1/trust/authority/tenants/acme/teams/platform/bundle",
                token="trust-token",
            )
            self.assertEqual(bundle_status, 501)
            self.assertEqual(bundle_payload["error"], "external signer provider is not implemented")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            shutil.rmtree(cwd, ignore_errors=True)

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

    def test_trust_service_sqlite_backend_persists_state_and_survives_restart(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-sqlite-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        db_file = cwd / ".agent" / "service" / "trust.sqlite3"
        authority_db_file = cwd / ".agent" / "service" / "trust-authority.sqlite3"

        with mock.patch("skillsmith.commands.trust_service._timestamp_to_string", return_value="2026-03-19T12:00:00Z"):
            server, thread, base_url = self._start_service(
                cwd,
                backend="sqlite",
                db_file=db_file,
                authority_db_file=authority_db_file,
            )
            try:
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
                    },
                )
                self.assertEqual(publish_status, 200)
                self.assertEqual(publish_payload["key"]["key_id"], "publisher-primary")

                trust_before_status, trust_before = self._request_json(base_url, "GET", "/v1/trust", token="trust-token")
                self.assertEqual(trust_before_status, 200)
                bootstrap_before_status, bootstrap_before = self._request_json(
                    base_url,
                    "GET",
                    "/v1/trust/authority/bootstrap",
                    token="trust-token",
                )
                self.assertEqual(bootstrap_before_status, 200)
                self.assertEqual(trust_before["keys"][0]["key_id"], "publisher-primary")
                self.assertEqual(bootstrap_before["trust_roots"][0]["key_id"], "root-1")
                self.assertEqual(self._read_sqlite_state(db_file)["keys"][0]["key_id"], "publisher-primary")
                self.assertEqual(self._read_sqlite_state(authority_db_file)["trust_roots"][0]["key_id"], "root-1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        with mock.patch("skillsmith.commands.trust_service._timestamp_to_string", return_value="2026-03-19T12:00:00Z"):
            server2, thread2, base_url2 = self._start_service(
                cwd,
                backend="sqlite",
                db_file=db_file,
                authority_db_file=authority_db_file,
            )
            try:
                trust_after_status, trust_after = self._request_json(base_url2, "GET", "/v1/trust", token="trust-token")
                self.assertEqual(trust_after_status, 200)
                bootstrap_after_status, bootstrap_after = self._request_json(
                    base_url2,
                    "GET",
                    "/v1/trust/authority/bootstrap",
                    token="trust-token",
                )
                self.assertEqual(bootstrap_after_status, 200)
                self.assertEqual(trust_after["keys"], trust_before["keys"])
                self.assertEqual(bootstrap_after["trust_roots"], bootstrap_before["trust_roots"])
            finally:
                server2.shutdown()
                server2.server_close()
                thread2.join(timeout=2)
                shutil.rmtree(cwd, ignore_errors=True)

    def test_trust_service_sqlite_backend_imports_legacy_json_once(self):
        self._temp_root.mkdir(parents=True, exist_ok=True)
        cwd = self._temp_root / f"trust-service-import-{uuid.uuid4().hex}"
        cwd.mkdir(parents=True, exist_ok=False)
        db_file = cwd / ".agent" / "service" / "trust.sqlite3"
        authority_db_file = cwd / ".agent" / "service" / "trust-authority.sqlite3"
        legacy_trust = {
            "service": "trust",
            "version": 1,
            "generated_at": "2026-03-18T09:00:00Z",
            "keys": [
                {
                    "tenant_id": "acme",
                    "team_id": "platform",
                    "key_id": "legacy-key",
                    "name": "Legacy Key",
                    "algorithm": "hmac-sha256",
                    "kind": "shared-secret",
                    "status": "active",
                    "material": "legacy-secret",
                    "history": [
                        {
                            "action": "publish",
                            "actor": "legacy-operator",
                            "at": "2026-03-18T09:00:00Z",
                            "from_state": None,
                            "to_state": "active",
                        }
                    ],
                }
            ],
            "revocations": [
                {
                    "tenant_id": "acme",
                    "team_id": "platform",
                    "key_id": "legacy-key",
                    "revoked_at": "2026-03-18T09:30:00Z",
                    "reason": "legacy-retired",
                    "actor": "legacy-operator",
                }
            ],
        }
        legacy_authority = {
            "service": "trust-authority",
            "version": 1,
            "generated_at": "2026-03-18T08:55:00Z",
            "authority_id": "legacy-authority",
            "trust_roots": [
                {
                    "key_id": "legacy-root",
                    "name": "legacy-root",
                    "algorithm": "hmac-sha256",
                    "secret": "legacy-secret",
                    "status": "active",
                    "created_at": "2026-03-18T08:55:00Z",
                    "updated_at": "2026-03-18T08:55:00Z",
                }
            ],
        }
        self._write_legacy_trust_json(cwd, legacy_trust)
        self._write_legacy_authority_json(cwd, legacy_authority)

        with mock.patch("skillsmith.commands.trust_service._timestamp_to_string", return_value="2026-03-19T12:00:00Z"):
            server, thread, base_url = self._start_service(
                cwd,
                backend="sqlite",
                db_file=db_file,
                authority_db_file=authority_db_file,
            )
            try:
                trust_status, trust_payload = self._request_json(base_url, "GET", "/v1/trust", token="trust-token")
                self.assertEqual(trust_status, 200)
                self.assertEqual(trust_payload["keys"][0]["key_id"], "legacy-key")
                self.assertEqual(trust_payload["revocations"][0]["reason"], "legacy-retired")

                bootstrap_status, bootstrap_payload = self._request_json(
                    base_url,
                    "GET",
                    "/v1/trust/authority/bootstrap",
                    token="trust-token",
                )
                self.assertEqual(bootstrap_status, 200)
                self.assertEqual(bootstrap_payload["authority_id"], "legacy-authority")
                self.assertEqual(bootstrap_payload["trust_roots"][0]["key_id"], "legacy-root")
                self.assertEqual(bootstrap_payload["trust_roots"][0]["secret"], "legacy-secret")
                self.assertEqual(self._read_sqlite_state(db_file)["keys"][0]["key_id"], "legacy-key")
                self.assertEqual(self._read_sqlite_state(authority_db_file)["trust_roots"][0]["key_id"], "legacy-root")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self._write_legacy_trust_json(
            cwd,
            {
                "service": "trust",
                "version": 1,
                "generated_at": "2026-03-20T09:00:00Z",
                "keys": [
                    {
                        "tenant_id": "beta",
                        "team_id": "ops",
                        "key_id": "changed-key",
                        "name": "Changed Key",
                        "algorithm": "hmac-sha256",
                        "kind": "shared-secret",
                        "status": "active",
                    }
                ],
                "revocations": [],
            },
        )
        self._write_legacy_authority_json(
            cwd,
            {
                "service": "trust-authority",
                "version": 1,
                "generated_at": "2026-03-20T09:00:00Z",
                "authority_id": "changed-authority",
                "trust_roots": [
                    {
                        "key_id": "changed-root",
                        "name": "changed-root",
                        "algorithm": "hmac-sha256",
                        "secret": "changed-secret",
                        "status": "active",
                        "created_at": "2026-03-20T09:00:00Z",
                        "updated_at": "2026-03-20T09:00:00Z",
                    }
                ],
            },
        )

        with mock.patch("skillsmith.commands.trust_service._timestamp_to_string", return_value="2026-03-19T12:00:00Z"):
            server2, thread2, base_url2 = self._start_service(
                cwd,
                backend="sqlite",
                db_file=db_file,
                authority_db_file=authority_db_file,
            )
            try:
                trust_status, trust_payload = self._request_json(base_url2, "GET", "/v1/trust", token="trust-token")
                self.assertEqual(trust_status, 200)
                self.assertEqual(trust_payload["keys"][0]["key_id"], "legacy-key")
                self.assertNotEqual(trust_payload["keys"][0]["key_id"], "changed-key")

                bootstrap_status, bootstrap_payload = self._request_json(
                    base_url2,
                    "GET",
                    "/v1/trust/authority/bootstrap",
                    token="trust-token",
                )
                self.assertEqual(bootstrap_status, 200)
                self.assertEqual(bootstrap_payload["authority_id"], "legacy-authority")
                self.assertEqual(bootstrap_payload["trust_roots"][0]["key_id"], "legacy-root")
                self.assertNotEqual(bootstrap_payload["trust_roots"][0]["key_id"], "changed-root")
            finally:
                server2.shutdown()
                server2.server_close()
                thread2.join(timeout=2)
                shutil.rmtree(cwd, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
