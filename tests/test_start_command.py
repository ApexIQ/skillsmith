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


class StartCommandTests(unittest.TestCase):
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

    def test_start_json_bootstraps_and_runs_wedge_path(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["start", "--json"])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["guided_init_requested"])
            self.assertTrue(payload["init"]["ran"])
            self.assertFalse(payload["init"]["skipped"])
            self.assertEqual(payload["readiness_summary"]["status"], "ready")
            self.assertGreaterEqual(int(payload["readiness_summary"]["score"]), 80)
            self.assertTrue((cwd / "AGENTS.md").exists())
            self.assertTrue((cwd / ".agent" / "project_profile.yaml").exists())
            self.assertTrue((cwd / ".agent" / "context" / "project-context.md").exists())

    def test_start_json_skips_bootstrap_when_workspace_exists(self):
        with self.project_dir():
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            result = self.runner.invoke(main, ["start", "--json"])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["init"]["ran"])
            self.assertTrue(payload["init"]["skipped"])

    def test_start_human_output_calls_out_default_path_and_artifacts(self):
        with self.project_dir():
            result = self.runner.invoke(main, ["start"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Start", result.output)
            self.assertIn("Default path: init -> doctor -> compose -> report", result.output)
            self.assertIn("Persist artifacts with `skillsmith report --artifact-dir .agent/readiness`.", result.output)


if __name__ == "__main__":
    unittest.main()
