import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class SafetyCommandTests(unittest.TestCase):
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

    def test_guard_persists_careful_and_freeze_target(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(
                main,
                ["safety", "guard", "--target", "review-only", "--reason", "protect release branch"],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            policy_path = cwd / ".agent" / "safety" / "policy.json"
            self.assertTrue(policy_path.exists())
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertTrue(policy["careful"])
            self.assertTrue(policy["freeze"]["enabled"])
            self.assertEqual(policy["freeze"]["target"], "review-only")
            self.assertEqual(policy["freeze"]["reason"], "protect release branch")

            status = self.runner.invoke(main, ["safety", "status"])
            self.assertEqual(status.exit_code, 0, status.output)
            self.assertIn("Safety Status", status.output)
            self.assertIn("enabled", status.output)
            self.assertIn("review-only", status.output)

    def test_unfreeze_keeps_careful_unless_disabled(self):
        with self.project_dir() as cwd:
            guard_result = self.runner.invoke(main, ["safety", "guard", "--target", "writes"])
            self.assertEqual(guard_result.exit_code, 0, guard_result.output)

            unfreeze_result = self.runner.invoke(main, ["safety", "unfreeze"])
            self.assertEqual(unfreeze_result.exit_code, 0, unfreeze_result.output)

            policy_path = cwd / ".agent" / "safety" / "policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertTrue(policy["careful"])
            self.assertFalse(policy["freeze"]["enabled"])
            self.assertEqual(policy["freeze"]["target"], "")
            self.assertEqual(policy["freeze"]["reason"], "")

            disable_result = self.runner.invoke(main, ["safety", "unfreeze", "--disable-careful"])
            self.assertEqual(disable_result.exit_code, 0, disable_result.output)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertFalse(policy["careful"])
            self.assertFalse(policy["freeze"]["enabled"])

    def test_careful_can_be_disabled_explicitly(self):
        with self.project_dir() as cwd:
            enable_result = self.runner.invoke(main, ["safety", "careful"])
            self.assertEqual(enable_result.exit_code, 0, enable_result.output)

            disable_result = self.runner.invoke(main, ["safety", "careful", "--disable"])
            self.assertEqual(disable_result.exit_code, 0, disable_result.output)

            policy_path = cwd / ".agent" / "safety" / "policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertFalse(policy["careful"])
            self.assertFalse(policy["freeze"]["enabled"])

    def test_freeze_defaults_to_all_writes(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["safety", "freeze"])

            self.assertEqual(result.exit_code, 0, result.output)
            policy_path = cwd / ".agent" / "safety" / "policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertFalse(policy["careful"])
            self.assertTrue(policy["freeze"]["enabled"])
            self.assertEqual(policy["freeze"]["target"], "all-writes")


if __name__ == "__main__":
    unittest.main()
