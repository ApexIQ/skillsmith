import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
import uuid

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class ProfilePolicyCliTests(unittest.TestCase):
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

    def test_init_guided_persists_policy_fields_into_profile_and_context(self):
        with self.project_dir() as cwd:
            user_input = "\n".join(
                [
                    "AI release automation platform",
                    "greenfield",
                    "saas",
                    "python, typescript",
                    "fastapi, next",
                    "uv",
                    "fly.io",
                    "speed, maintainability",
                    "codex, claude, cursor",
                    "y",
                    "local, github, skills.sh",
                    "github, gitlab",
                    "y",
                    "",
                    "publisher-demo=publisher-secret",
                    "auto",
                    "",
                    "required",
                    "81",
                    "12",
                    "",
                    "MIT, Apache-2.0",
                ]
            )

            result = self.runner.invoke(main, ["init", "--minimal", "--guided"], input=user_input + "\n")

            self.assertEqual(result.exit_code, 0, result.output)

            profile = yaml.safe_load((cwd / ".agent" / "project_profile.yaml").read_text(encoding="utf-8"))
            context_text = (cwd / ".agent" / "context" / "project-context.md").read_text(encoding="utf-8")

            self.assertTrue(profile["allow_remote_skills"])
            self.assertEqual(profile["trusted_skill_sources"], ["local", "github", "skills.sh"])
            self.assertEqual(profile["blocked_skill_sources"], ["github", "gitlab"])
            self.assertTrue(profile["require_pinned_github_refs"])
            self.assertEqual(profile["trusted_publisher_keys"], {"publisher-demo": "publisher-secret"})
            self.assertEqual(profile["trusted_publisher_public_keys"], {})
            self.assertEqual(profile["publisher_signature_scheme_mode"], "auto")
            self.assertEqual(profile["publisher_signature_algorithms"], ["hmac-sha256", "rsa-sha256"])
            self.assertEqual(profile["publisher_key_rotation"], {})
            self.assertEqual(profile["publisher_verification_mode"], "required")
            self.assertEqual(profile["min_remote_trust_score"], 81)
            self.assertEqual(profile["min_remote_freshness_score"], 12)
            self.assertEqual(profile["required_remote_licenses"], ["MIT", "Apache-2.0"])
            self.assertIn("Allow remote skills: true", context_text)
            self.assertIn("Trusted sources: local, github, skills.sh", context_text)
            self.assertIn("Blocked sources: github, gitlab", context_text)
            self.assertIn("Require pinned GitHub refs: true", context_text)
            self.assertIn("Trusted publisher keys: publisher-demo", context_text)
            self.assertIn("Trusted publisher public keys: none", context_text)
            self.assertIn("Publisher signature scheme mode: auto", context_text)
            self.assertIn("Allowed publisher signature algorithms: hmac-sha256, rsa-sha256", context_text)
            self.assertIn("Publisher key rotation: none", context_text)
            self.assertIn("Publisher verification mode: required", context_text)
            self.assertIn("Minimum remote trust: 81", context_text)
            self.assertIn("Minimum remote freshness: 12", context_text)
            self.assertIn("Required remote licenses: MIT, Apache-2.0", context_text)

    def test_profile_set_roundtrips_policy_fields_through_show(self):
        with self.project_dir():
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            set_result = self.runner.invoke(
                main,
                [
                    "profile",
                    "set",
                    "--trusted-skill-sources",
                    "local,skills.sh",
                    "--trusted-skill-sources",
                    "github",
                    "--blocked-skill-sources",
                    "github,gitlab",
                    "--allow-unpinned-github-refs",
                    "--trusted-publisher-keys",
                    "publisher-a=secret-a,publisher-b=secret-b",
                    "--trusted-publisher-public-keys",
                    "publisher-rsa=abcdef1234:65537",
                    "--publisher-signature-scheme-mode",
                    "rsa",
                    "--publisher-signature-algorithms",
                    "rsa-sha256",
                    "--publisher-verification-mode",
                    "required",
                    "--publisher-key-rotation",
                    "current_key_id=publisher-rsa,previous_key_ids=publisher-old|publisher-older,rotation_grace_period_days=30",
                    "--min-remote-trust-score",
                    "82",
                    "--min-remote-freshness-score",
                    "9",
                    "--required-remote-licenses",
                    "MIT,Apache-2.0",
                ],
            )

            self.assertEqual(set_result.exit_code, 0, set_result.output)
            self.assertIn("trusted_skill_sources=['local', 'skills.sh', 'github']", set_result.output)
            self.assertIn("min_remote_trust_score=82", set_result.output)
            self.assertIn("blocked_skill_sources=['github', 'gitlab']", set_result.output)
            self.assertIn("require_pinned_github_refs=False", set_result.output)
            self.assertIn("trusted_publisher_keys=['publisher-a', 'publisher-b']", set_result.output)
            self.assertIn("trusted_publisher_public_keys=['publisher-rsa']", set_result.output)
            self.assertIn("publisher_signature_scheme_mode=rsa", set_result.output)
            self.assertIn("publisher_signature_algorithms=['rsa-sha256']", set_result.output)
            self.assertIn("publisher_verification_mode=required", set_result.output)
            self.assertIn("publisher_key_rotation=current=publisher-rsa", set_result.output)
            self.assertIn("previous=publisher-old,publisher-older", set_result.output)
            self.assertIn("grace=30", set_result.output)
            self.assertIn("min_remote_freshness_score=9", set_result.output)
            self.assertIn("required_remote_licenses=['MIT', 'Apache-2.0']", set_result.output)

            profile = yaml.safe_load(Path(".agent/project_profile.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profile["trusted_skill_sources"], ["local", "skills.sh", "github"])
            self.assertEqual(profile["blocked_skill_sources"], ["github", "gitlab"])
            self.assertFalse(profile["require_pinned_github_refs"])
            self.assertEqual(profile["trusted_publisher_keys"], {"publisher-a": "secret-a", "publisher-b": "secret-b"})
            self.assertEqual(profile["trusted_publisher_public_keys"], {"publisher-rsa": {"n": "abcdef1234", "e": 65537}})
            self.assertEqual(profile["publisher_signature_scheme_mode"], "rsa")
            self.assertEqual(profile["publisher_signature_algorithms"], ["rsa-sha256"])
            self.assertEqual(profile["publisher_verification_mode"], "required")
            self.assertEqual(
                profile["publisher_key_rotation"],
                {
                    "current_key_id": "publisher-rsa",
                    "previous_key_ids": ["publisher-old", "publisher-older"],
                    "rotation_grace_period_days": 30,
                },
            )
            self.assertEqual(profile["min_remote_trust_score"], 82)
            self.assertEqual(profile["min_remote_freshness_score"], 9)
            self.assertEqual(profile["required_remote_licenses"], ["MIT", "Apache-2.0"])

            show_result = self.runner.invoke(main, ["profile", "show"])
            self.assertEqual(show_result.exit_code, 0, show_result.output)
            self.assertIn("loaded from .agent/project_profile.yaml", show_result.output)
            self.assertIn("trusted_skill_sources:", show_result.output)
            self.assertIn("blocked_skill_sources:", show_result.output)
            self.assertIn("- skills.sh", show_result.output)
            self.assertIn("require_pinned_github_refs: false", show_result.output)
            self.assertIn("trusted_publisher_keys:", show_result.output)
            self.assertIn("trusted_publisher_public_keys:", show_result.output)
            self.assertIn("publisher_signature_scheme_mode: rsa", show_result.output)
            self.assertIn("publisher_signature_algorithms:", show_result.output)
            self.assertIn("publisher_verification_mode: required", show_result.output)
            self.assertIn("publisher_key_rotation:", show_result.output)
            self.assertIn("min_remote_trust_score: 82", show_result.output)
            self.assertIn("min_remote_freshness_score: 9", show_result.output)
            self.assertIn("required_remote_licenses:", show_result.output)


if __name__ == "__main__":
    unittest.main()
