import json
import hashlib
import hmac
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
import uuid
from unittest import mock

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main
from skillsmith.commands.providers import SkillCandidate


class IntegrationE2ETests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @contextmanager
    def project_dir(self):
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

    def test_e2e_local_flow_init_to_eval(self):
        with self.project_dir() as cwd, mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "integration-secret"}, clear=False
        ):
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            add_result = self.runner.invoke(main, ["add", "atomic_execution"])
            self.assertEqual(add_result.exit_code, 0, add_result.output)

            align_result = self.runner.invoke(main, ["align"])
            self.assertEqual(align_result.exit_code, 0, align_result.output)

            doctor_result = self.runner.invoke(main, ["doctor"])
            self.assertEqual(doctor_result.exit_code, 0, doctor_result.output)
            self.assertIn("lockfile signature valid", doctor_result.output)

            audit_result = self.runner.invoke(main, ["audit", "--json"])
            self.assertEqual(audit_result.exit_code, 0, audit_result.output)
            audit_payload = json.loads(audit_result.output)
            self.assertIn("summary", audit_payload)

            report_result = self.runner.invoke(main, ["report"])
            self.assertEqual(report_result.exit_code, 0, report_result.output)

            runs_path = cwd / ".agent" / "evals" / "runs.json"
            runs_path.parent.mkdir(parents=True, exist_ok=True)
            runs_path.write_text(
                json.dumps({"runs": [{"id": "r1", "tests_passed": True, "policy_passed": True, "rollback_required": False}]}),
                encoding="utf-8",
            )
            eval_result = self.runner.invoke(main, ["eval"])
            self.assertEqual(eval_result.exit_code, 0, eval_result.output)
            self.assertTrue((cwd / ".agent" / "evals" / "results" / "latest.json").exists())

    def test_e2e_discovery_install_with_pinned_github_url(self):
        with self.project_dir() as cwd:
            self.assertEqual(self.runner.invoke(main, ["init", "--minimal"]).exit_code, 0)
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            profile["allow_remote_skills"] = True
            profile["trusted_skill_sources"] = ["local", "skills.sh"]
            profile["allowed_remote_domains"] = ["github.com"]
            profile["require_pinned_github_refs"] = True
            profile["trusted_publisher_keys"] = {"publisher-demo": "publisher-secret"}
            profile["publisher_verification_mode"] = "required"
            profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

            candidate = SkillCandidate(
                name="remote-packaging",
                description="Remote packaging flow",
                source="skills.sh",
                install_ref="org/repo@remote-packaging",
                trust_score=75,
                metadata={
                    "install_url": "https://github.com/example/repo/tree/0123456789abcdef0123456789abcdef01234567/remote-packaging"
                },
            )

            def fake_download(url, target):
                target.mkdir(parents=True, exist_ok=True)
                skill_path = target / "SKILL.md"
                skill_path.write_text("---\nname: remote-packaging\ndescription: test\nversion: 1.0.0\n---\nbody", encoding="utf-8")
                manifest = {
                    "algorithm": "sha256",
                    "files": [
                        {
                            "path": "SKILL.md",
                            "sha256": hashlib.sha256(skill_path.read_bytes()).hexdigest(),
                        }
                    ],
                }
                manifest_text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                (target / "skillsmith.manifest.json").write_text(manifest_text, encoding="utf-8")
                signature = hmac.new(
                    "publisher-secret".encode("utf-8"), manifest_text.encode("utf-8"), hashlib.sha256
                ).hexdigest()
                (target / "skillsmith.sig").write_text(
                    json.dumps({"algorithm": "hmac-sha256", "key_id": "publisher-demo", "signature": signature}, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )

            with mock.patch("skillsmith.commands.add.discover_skills", return_value=[candidate]), mock.patch(
                "skillsmith.commands.add.download_github_dir", side_effect=fake_download
            ):
                result = self.runner.invoke(main, ["add", "remote packaging", "--discover"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((cwd / ".agent" / "skills" / "remote-packaging" / "SKILL.md").exists())
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["name"], "remote-packaging")
            self.assertEqual(entry["source"], "skills.sh")
            self.assertIn("source_domain", entry["provenance"])
            self.assertTrue(entry["provenance"].get("pinned_ref"))
            self.assertEqual(entry["metadata"]["publisher_verification"]["state"], "valid")
            self.assertEqual(entry["provenance"]["publisher_verification_method"], "shared-secret")
            self.assertEqual(entry["provenance"]["publisher_verification_algorithm"], "hmac-sha256")


if __name__ == "__main__":
    unittest.main()
