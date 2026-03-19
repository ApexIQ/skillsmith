from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import shutil
from pathlib import Path
import uuid
from contextlib import contextmanager
from unittest import TestCase, mock

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main
from skillsmith.commands.doctor import doctor_command
from skillsmith.commands.lockfile import (
    _legacy_checksum_for_path,
    _reason_hash,
    _timestamp_to_string,
    verify_remote_skill_artifact,
    verify_lockfile_signature,
    refresh_local_lockfile_verification_timestamps,
    record_skill_install,
    write_lockfile,
)
from skillsmith.commands.providers import SkillCandidate


_RSA_PUBLIC_MODULUS_HEX = "d5c483aeceaa7884864aebe5764f96e524ad6b761a7f843ad521c2d86f5bb94240c2d2b68a28426a3b7d09ade192bd95d3dfedd59240f3f3ba7fd3f01dbf6e3d"
_RSA_PRIVATE_EXPONENT_HEX = "49351f93c21b0762fb4ab536c429c5977bd418353e25e576f07ebb67bbdb41ba1a0e62208e0a668c0baf5fdeb084545a90a4ef1f4210e3391f49d2d3f84b51d1"
_RSA_PUBLIC_EXPONENT = 65537
_RSA_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


class LockfileIntegrityTests(TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.runner.isolated_filesystem = self._isolated_filesystem

    @contextmanager
    def _isolated_filesystem(self):
        root = Path.cwd() / ".test-tmp"
        root.mkdir(exist_ok=True)
        cwd = root / uuid.uuid4().hex
        cwd.mkdir()
        previous = Path.cwd()
        os.chdir(cwd)
        try:
            yield cwd
        finally:
            os.chdir(previous)
            shutil.rmtree(cwd, ignore_errors=True)

    def _write_skill(self, cwd: Path, name: str, body: str = "# Skill") -> Path:
        skill_dir = cwd / ".agent" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
        return skill_dir

    def _write_signed_remote_skill(self, cwd: Path, name: str, *, key_id: str = "publisher-demo", key: str = "publisher-secret") -> Path:
        skill_dir = self._write_skill(cwd, name, body="---\nname: signed-skill\ndescription: test\nversion: 1.0.0\n---\nbody")
        manifest = {
            "algorithm": "sha256",
            "files": [
                {
                    "path": "SKILL.md",
                    "sha256": hashlib.sha256((skill_dir / "SKILL.md").read_bytes()).hexdigest(),
                }
            ],
        }
        manifest_text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        (skill_dir / "skillsmith.manifest.json").write_text(manifest_text, encoding="utf-8")
        signature = hmac.new(key.encode("utf-8"), manifest_text.encode("utf-8"), hashlib.sha256).hexdigest()
        (skill_dir / "skillsmith.sig").write_text(
            json.dumps({"algorithm": "hmac-sha256", "key_id": key_id, "signature": signature}, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return skill_dir

    def _rsa_sign(self, payload: bytes) -> str:
        modulus = int(_RSA_PUBLIC_MODULUS_HEX, 16)
        private_exponent = int(_RSA_PRIVATE_EXPONENT_HEX, 16)
        digest = hashlib.sha256(payload).digest()
        key_length = (modulus.bit_length() + 7) // 8
        padding_length = key_length - len(_RSA_SHA256_PREFIX) - len(digest) - 3
        encoded = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + _RSA_SHA256_PREFIX + digest
        signature_int = pow(int.from_bytes(encoded, "big"), private_exponent, modulus)
        return signature_int.to_bytes(key_length, "big").hex()

    def _write_rsa_signed_remote_skill(
        self,
        cwd: Path,
        name: str,
        *,
        key_id: str = "publisher-rsa",
        valid: bool = True,
    ) -> Path:
        skill_dir = self._write_skill(cwd, name, body="---\nname: signed-skill\ndescription: test\nversion: 1.0.0\n---\nbody")
        manifest = {
            "algorithm": "sha256",
            "files": [
                {
                    "path": "SKILL.md",
                    "sha256": hashlib.sha256((skill_dir / "SKILL.md").read_bytes()).hexdigest(),
                }
            ],
        }
        manifest_text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        (skill_dir / "skillsmith.manifest.json").write_text(manifest_text, encoding="utf-8")
        signature = self._rsa_sign(manifest_text.encode("utf-8"))
        if not valid:
            signature = "0" * len(signature)
        (skill_dir / "skillsmith.sig").write_text(
            json.dumps({"algorithm": "rsa-sha256", "key_id": key_id, "signature": signature}, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return skill_dir

    def _write_publisher_revocations(self, cwd: Path, revoked_key_ids: list[str]) -> Path:
        trust_dir = cwd / ".agent" / "trust"
        trust_dir.mkdir(parents=True, exist_ok=True)
        path = trust_dir / "publisher_revocations.json"
        path.write_text(json.dumps({"revoked_key_ids": revoked_key_ids}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return path

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

    def _write_authority_bootstrap(self, cwd: Path, *, root_key_id: str = "root-1", root_secret: str = "authority-root-secret") -> Path:
        authority_dir = cwd / ".agent" / "trust" / "authority"
        authority_dir.mkdir(parents=True, exist_ok=True)
        path = authority_dir / "bootstrap.json"
        payload = {
            "service": "trust-authority",
            "version": 1,
            "generated_at": "2026-03-19T12:00:00Z",
            "authority_id": "local",
            "trust_roots": [
                {
                    "key_id": root_key_id,
                    "name": root_key_id,
                    "algorithm": "hmac-sha256",
                    "secret": root_secret,
                    "status": "active",
                }
            ],
        }
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return path

    def _write_authority_bundle(
        self,
        cwd: Path,
        *,
        tenant_id: str,
        team_id: str,
        keys: list[dict],
        root_key_id: str = "root-1",
        root_secret: str = "authority-root-secret",
        valid: bool = True,
    ) -> Path:
        authority_dir = cwd / ".agent" / "trust" / "authority"
        authority_dir.mkdir(parents=True, exist_ok=True)
        path = authority_dir / "bundle.json"
        payload = {
            "service": "trust-authority",
            "version": 1,
            "generated_at": "2026-03-19T12:00:00Z",
            "tenant_id": tenant_id,
            "team_id": team_id,
            "keys": keys,
        }
        digest, signature = self._authority_signature(payload, root_secret)
        if not valid:
            signature = "0" * len(signature)
        payload["signature"] = {
            "algorithm": "hmac-sha256",
            "key_id": root_key_id,
            "digest": digest,
            "signature": signature,
            "signed_at": "2026-03-19T12:00:00Z",
        }
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return path

    def _write_authority_revocations(
        self,
        cwd: Path,
        *,
        tenant_id: str,
        team_id: str,
        revoked_key_ids: list[str],
        root_key_id: str = "root-1",
        root_secret: str = "authority-root-secret",
        valid: bool = True,
    ) -> Path:
        authority_dir = cwd / ".agent" / "trust" / "authority"
        authority_dir.mkdir(parents=True, exist_ok=True)
        path = authority_dir / "revocations.json"
        payload = {
            "service": "trust-authority",
            "version": 1,
            "generated_at": "2026-03-19T12:00:00Z",
            "tenant_id": tenant_id,
            "team_id": team_id,
            "revocations": [{"key_id": key_id} for key_id in revoked_key_ids],
        }
        digest, signature = self._authority_signature(payload, root_secret)
        if not valid:
            signature = "0" * len(signature)
        payload["signature"] = {
            "algorithm": "hmac-sha256",
            "key_id": root_key_id,
            "digest": digest,
            "signature": signature,
            "signed_at": "2026-03-19T12:00:00Z",
        }
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return path

    def test_record_skill_install_persists_recommendation_metadata_and_verification_timestamp(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_skill(cwd, "atomic_execution")
            candidate = SkillCandidate(
                name="atomic_execution",
                description="Execute plans in small reliable steps",
                source="local",
                version="1.0.0",
                install_ref="atomic_execution",
                trust_score=87,
                metadata={
                    "recommendation": {
                        "reasons": ["starter pack match", "query fit"],
                        "selected_by": "skillsmith",
                    }
                },
            )
            fixed_now = datetime.datetime(2026, 3, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)

            with mock.patch("skillsmith.commands.lockfile._utc_now", return_value=fixed_now):
                record_skill_install(cwd, candidate, skill_dir)

            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            expected_hash = hashlib.sha256(
                json.dumps(["starter pack match", "query fit"], separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest()

            self.assertEqual(entry["verification_timestamp"], _timestamp_to_string(fixed_now))
            self.assertEqual(lockfile["schema_version"], 2)
            self.assertEqual(entry["recommendation"]["score"], 87)
            self.assertEqual(entry["recommendation"]["reason_hash"], expected_hash)
            self.assertEqual(entry["recommendation"]["reason_hash"], _reason_hash(["starter pack match", "query fit"]))

    def test_refresh_local_lockfile_verification_timestamps_handles_legacy_entries(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            stale_skill = self._write_skill(cwd, "legacy_stale")
            unverified_skill = self._write_skill(cwd, "legacy_unverified")

            stale_checksum = hashlib.sha256((stale_skill / "SKILL.md").read_bytes()).hexdigest()
            unverified_checksum = hashlib.sha256((unverified_skill / "SKILL.md").read_bytes()).hexdigest()
            payload = {
                "version": 1,
                "skills": [
                    {
                        "name": "legacy_stale",
                        "source": "local",
                        "path": ".agent/skills/legacy_stale",
                        "checksum": stale_checksum,
                        "installed_at": "2025-01-01T00:00:00Z",
                        "verification_timestamp": "2025-01-01T00:00:00Z",
                        "recommendation": {"reasons": ["manual install"]},
                    },
                    {
                        "name": "legacy_unverified",
                        "source": "local",
                        "path": ".agent/skills/legacy_unverified",
                        "checksum": unverified_checksum,
                        "installed_at": "2025-01-01T00:00:00Z",
                        "recommendation": {"reasons": ["manual install"]},
                    },
                ],
            }
            fixed_now = datetime.datetime(2026, 3, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)

            refreshed, findings, changed = refresh_local_lockfile_verification_timestamps(
                cwd,
                payload,
                now=fixed_now,
                stale_after_days=30,
            )

            self.assertTrue(changed)
            self.assertEqual(findings[0]["state"], "stale")
            self.assertEqual(findings[1]["state"], "unverified")
            self.assertEqual(refreshed["skills"][0]["verification_timestamp"], _timestamp_to_string(fixed_now))
            self.assertEqual(refreshed["skills"][1]["verification_timestamp"], _timestamp_to_string(fixed_now))

    def test_doctor_refreshes_stale_local_verification_timestamp_and_reports_it(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(result.exit_code, 0, result.output)

            skill_dir = self._write_skill(cwd, "local_check")
            candidate = SkillCandidate(
                name="local_check",
                description="Checksum verified local skill",
                source="local",
                version="1.0.0",
                install_ref="local_check",
                trust_score=90,
                metadata={"recommendation": {"reasons": ["manual install"], "selected_by": "skillsmith"}},
            )
            install_time = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
            doctor_time = datetime.datetime(2026, 3, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)

            with mock.patch("skillsmith.commands.lockfile._utc_now", return_value=install_time):
                record_skill_install(cwd, candidate, skill_dir)

            lockfile_path = cwd / "skills.lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            target_entry = next(item for item in lockfile["skills"] if item["name"] == "local_check")
            target_entry["verification_timestamp"] = "2025-01-01T00:00:00Z"
            lockfile_path.write_text(json.dumps(lockfile), encoding="utf-8")

            with mock.patch("skillsmith.commands.lockfile._utc_now", return_value=doctor_time), mock.patch(
                "skillsmith.commands.doctor.shutil.which", return_value="skillsmith"
            ):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("verification timestamp was stale", result.output)
            self.assertIn(_timestamp_to_string(doctor_time), result.output)

            updated_lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            refreshed_entry = next(item for item in updated_lockfile["skills"] if item["name"] == "local_check")
            self.assertEqual(refreshed_entry["verification_timestamp"], _timestamp_to_string(doctor_time))

    def test_refresh_detects_tampering_in_non_skill_file(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_skill(cwd, "manifest_skill")
            helper_file = skill_dir / "helper.py"
            helper_file.write_text("print('ok')\n", encoding="utf-8")
            candidate = SkillCandidate(
                name="manifest_skill",
                description="Directory manifest hash should detect file tampering",
                source="local",
                version="1.0.0",
                install_ref="manifest_skill",
                trust_score=90,
                metadata={"recommendation": {"reasons": ["manual install"]}},
            )

            record_skill_install(cwd, candidate, skill_dir)
            helper_file.write_text("print('changed')\n", encoding="utf-8")
            payload = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            refreshed, findings, changed = refresh_local_lockfile_verification_timestamps(cwd, payload)

            self.assertFalse(changed)
            self.assertEqual(refreshed["skills"][0]["name"], "manifest_skill")
            self.assertEqual(findings[0]["state"], "checksum-mismatch")

    def test_refresh_accepts_legacy_skill_md_checksum(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_skill(cwd, "legacy_checksum")
            payload = {
                "version": 1,
                "skills": [
                    {
                        "name": "legacy_checksum",
                        "source": "local",
                        "path": ".agent/skills/legacy_checksum",
                        "checksum": _legacy_checksum_for_path(skill_dir),
                        "verification_timestamp": "2026-03-01T00:00:00Z",
                    }
                ],
            }
            refreshed, findings, changed = refresh_local_lockfile_verification_timestamps(cwd, payload)

            self.assertFalse(changed)
            self.assertEqual(refreshed["skills"][0]["name"], "legacy_checksum")
            self.assertEqual(findings[0]["state"], "verified")

    def test_write_lockfile_uses_atomic_replace(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            payload = {"skills": [{"name": "example", "source": "local"}]}
            with mock.patch("skillsmith.commands.lockfile.os.replace") as replace_mock:
                write_lockfile(cwd, payload)
            replace_mock.assert_called_once()

    def test_write_lockfile_adds_signature_when_key_is_configured(self):
        with self.runner.isolated_filesystem(), mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "test-secret"}, clear=False
        ):
            cwd = Path.cwd()
            write_lockfile(cwd, {"skills": [{"name": "example", "source": "local"}]})

            payload = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            self.assertIn("signature", payload)
            self.assertEqual(payload["signature"]["algo"], "hmac-sha256")
            verification = verify_lockfile_signature(payload)
            self.assertTrue(verification["valid"])
            self.assertEqual(verification["state"], "valid")

    def test_verify_remote_skill_artifact_accepts_signed_manifest(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_signed")
            verification = verify_remote_skill_artifact(
                skill_dir,
                {"trusted_publisher_keys": {"publisher-demo": "publisher-secret"}, "publisher_verification_mode": "required"},
            )

            self.assertTrue(verification["valid"])
            self.assertEqual(verification["state"], "valid")
            self.assertEqual(verification["key_id"], "publisher-demo")
            self.assertEqual(verification["mode"], "required")
            self.assertEqual(verification["scheme"], "hmac")
            self.assertEqual(verification["method"], "shared-secret")

    def test_verify_remote_skill_artifact_accepts_rsa_signed_manifest(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_rsa_signed_remote_skill(cwd, "remote_rsa")
            verification = verify_remote_skill_artifact(
                skill_dir,
                {
                    "publisher_verification_mode": "required",
                    "publisher_signature_scheme_mode": "rsa",
                    "publisher_signature_algorithms": ["rsa-sha256"],
                    "trusted_publisher_public_keys": {
                        "publisher-rsa": {"n": _RSA_PUBLIC_MODULUS_HEX, "e": _RSA_PUBLIC_EXPONENT}
                    },
                },
            )

            self.assertTrue(verification["valid"])
            self.assertEqual(verification["state"], "valid")
            self.assertEqual(verification["key_id"], "publisher-rsa")
            self.assertEqual(verification["mode"], "required")
            self.assertEqual(verification["scheme"], "rsa")
            self.assertEqual(verification["method"], "public-key")
            self.assertEqual(verification["algorithm"], "rsa-sha256")

    def test_verify_remote_skill_artifact_rejects_invalid_rsa_signature(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_rsa_signed_remote_skill(cwd, "remote_rsa", valid=False)
            verification = verify_remote_skill_artifact(
                skill_dir,
                {
                    "publisher_verification_mode": "required",
                    "publisher_signature_scheme_mode": "rsa",
                    "publisher_signature_algorithms": ["rsa-sha256"],
                    "trusted_publisher_public_keys": {
                        "publisher-rsa": {"n": _RSA_PUBLIC_MODULUS_HEX, "e": _RSA_PUBLIC_EXPONENT}
                    },
                },
            )

            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "invalid")
            self.assertEqual(verification["scheme"], "rsa")
            self.assertEqual(verification["method"], "public-key")
            self.assertIn("publisher signature mismatch", verification["message"])

    def test_verify_remote_skill_artifact_falls_back_to_hmac_in_auto_mode(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_hmac")
            verification = verify_remote_skill_artifact(
                skill_dir,
                {
                    "publisher_verification_mode": "required",
                    "publisher_signature_scheme_mode": "auto",
                    "publisher_signature_algorithms": ["hmac-sha256", "rsa-sha256"],
                    "trusted_publisher_keys": {"publisher-demo": "publisher-secret"},
                    "trusted_publisher_public_keys": {
                        "publisher-rsa": {"n": _RSA_PUBLIC_MODULUS_HEX, "e": _RSA_PUBLIC_EXPONENT}
                    },
                },
            )

            self.assertTrue(verification["valid"])
            self.assertEqual(verification["state"], "valid")
            self.assertEqual(verification["key_id"], "publisher-demo")
            self.assertEqual(verification["scheme"], "hmac")
            self.assertEqual(verification["method"], "shared-secret")
            self.assertEqual(verification["algorithm"], "hmac-sha256")

    def test_verify_remote_skill_artifact_rejects_revoked_publisher_key(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_signed")
            self._write_publisher_revocations(cwd, ["publisher-demo"])

            verification = verify_remote_skill_artifact(
                skill_dir,
                {"trusted_publisher_keys": {"publisher-demo": "publisher-secret"}, "publisher_verification_mode": "required"},
            )

            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "revoked")
            self.assertEqual(verification["key_id"], "publisher-demo")
            self.assertIn("revoked", verification["message"])

            log_path = cwd / ".agent" / "trust" / "transparency_log.jsonl"
            log_lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(log_lines), 1)
            log_entry = json.loads(log_lines[0])
            self.assertEqual(log_entry["state"], "revoked")
            self.assertEqual(log_entry["key_id"], "publisher-demo")

    def test_verify_remote_skill_artifact_accepts_trusted_key_from_authority_bundle(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_authority", key_id="authority-demo", key="authority-secret")
            self._write_authority_bootstrap(cwd)
            self._write_authority_bundle(
                cwd,
                tenant_id="acme",
                team_id="platform",
                keys=[
                    {
                        "key_id": "authority-demo",
                        "algorithm": "hmac-sha256",
                        "kind": "shared-secret",
                        "material": "authority-secret",
                    }
                ],
            )

            verification = verify_remote_skill_artifact(skill_dir, {"publisher_verification_mode": "required"})

            self.assertTrue(verification["valid"])
            self.assertEqual(verification["state"], "valid")
            self.assertIn("authority-demo", verification["trusted_publisher_key_ids"])
            self.assertTrue(verification["trust_health"]["authority"]["bundle"]["valid"])

    def test_verify_remote_skill_artifact_rejects_authority_revoked_key(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_revoked", key_id="authority-revoked", key="authority-secret")
            self._write_authority_bootstrap(cwd)
            self._write_authority_bundle(
                cwd,
                tenant_id="acme",
                team_id="platform",
                keys=[
                    {
                        "key_id": "authority-revoked",
                        "algorithm": "hmac-sha256",
                        "kind": "shared-secret",
                        "material": "authority-secret",
                    }
                ],
            )
            self._write_authority_revocations(cwd, tenant_id="acme", team_id="platform", revoked_key_ids=["authority-revoked"])

            verification = verify_remote_skill_artifact(skill_dir, {"publisher_verification_mode": "required"})

            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "revoked")
            self.assertEqual(verification["key_id"], "authority-revoked")
            self.assertIn("revoked", verification["message"])

    def test_verify_remote_skill_artifact_flags_invalid_authority_signature(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_invalid_authority", key_id="authority-invalid", key="authority-secret")
            self._write_authority_bootstrap(cwd)
            self._write_authority_bundle(
                cwd,
                tenant_id="acme",
                team_id="platform",
                keys=[
                    {
                        "key_id": "authority-invalid",
                        "algorithm": "hmac-sha256",
                        "kind": "shared-secret",
                        "material": "authority-secret",
                    }
                ],
                valid=False,
            )

            verification = verify_remote_skill_artifact(skill_dir, {"publisher_verification_mode": "required"})

            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "untrusted")
            self.assertNotIn("authority-invalid", verification["trusted_publisher_key_ids"])
            self.assertFalse(verification["trust_health"]["authority"]["bundle"]["valid"])
            self.assertIn("authority signature", " ".join(verification["trust_health"]["authority"]["bundle"]["issues"]))

    def test_verify_remote_skill_artifact_appends_transparency_log_entries(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_signed_remote_skill(cwd, "remote_signed")

            first = verify_remote_skill_artifact(
                skill_dir,
                {"trusted_publisher_keys": {"publisher-demo": "publisher-secret"}, "publisher_verification_mode": "required"},
            )
            second = verify_remote_skill_artifact(
                skill_dir,
                {"trusted_publisher_keys": {"publisher-demo": "publisher-secret"}, "publisher_verification_mode": "required"},
            )

            self.assertTrue(first["valid"])
            self.assertTrue(second["valid"])

            log_path = cwd / ".agent" / "trust" / "transparency_log.jsonl"
            log_lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(log_lines), 2)
            first_entry = json.loads(log_lines[0])
            second_entry = json.loads(log_lines[1])
            self.assertEqual(first_entry["state"], "valid")
            self.assertEqual(second_entry["state"], "valid")
            self.assertEqual(first_entry["key_id"], "publisher-demo")
            self.assertEqual(second_entry["key_id"], "publisher-demo")

    def test_record_skill_install_persists_publisher_verification_metadata(self):
        with self.runner.isolated_filesystem():
            cwd = Path.cwd()
            skill_dir = self._write_skill(cwd, "remote_signed")
            candidate = SkillCandidate(
                name="remote_signed",
                description="Remote signed skill",
                source="github",
                version="1.0.0",
                install_ref="example/repo/tree/0123456789abcdef0123456789abcdef01234567/remote_signed",
                trust_score=90,
                metadata={
                    "publisher_verification": {
                        "state": "valid",
                        "mode": "required",
                        "key_id": "publisher-demo",
                        "algorithm": "hmac-sha256",
                        "method": "shared-secret",
                        "message": "publisher verification valid",
                    },
                    "provenance": {
                        "publisher_verification": {
                            "state": "valid",
                            "mode": "required",
                            "key_id": "publisher-demo",
                            "algorithm": "hmac-sha256",
                            "method": "shared-secret",
                        }
                    },
                },
            )

            record_skill_install(cwd, candidate, skill_dir)

            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["metadata"]["publisher_verification"]["state"], "valid")
            self.assertEqual(entry["provenance"]["publisher_verification"]["key_id"], "publisher-demo")
            self.assertEqual(entry["provenance"]["publisher_verification_method"], "shared-secret")
            self.assertEqual(entry["provenance"]["publisher_verification_algorithm"], "hmac-sha256")

    def test_verify_lockfile_signature_detects_tampering(self):
        with self.runner.isolated_filesystem(), mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "test-secret"}, clear=False
        ):
            cwd = Path.cwd()
            write_lockfile(cwd, {"skills": [{"name": "example", "source": "local"}]})
            path = cwd / "skills.lock.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["skills"][0]["name"] = "tampered-example"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            tampered = json.loads(path.read_text(encoding="utf-8"))
            verification = verify_lockfile_signature(tampered)
            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "invalid")

    def test_verify_lockfile_signature_reports_unsigned_when_key_is_set(self):
        with self.runner.isolated_filesystem(), mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "test-secret"}, clear=False
        ):
            payload = {"version": 1, "schema_version": 2, "skills": []}
            verification = verify_lockfile_signature(payload)
            self.assertFalse(verification["valid"])
            self.assertEqual(verification["state"], "unsigned")
