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


READY_WORKFLOW_PATH = Path(".github/workflows/skillsmith-ready.yml")


class ReadyCommandTests(unittest.TestCase):
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

    def test_ready_json_succeeds_after_minimal_init(self):
        with self.project_dir():
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            result = self.runner.invoke(main, ["ready", "--json"])
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["readiness_summary"]["status"], "ready")
            self.assertGreaterEqual(int(payload["readiness_summary"]["score"]), 80)
            self.assertIn("init", payload)
            self.assertIn("doctor", payload)
            self.assertIn("compose", payload)
            self.assertIn("report", payload)

    def test_ready_json_fails_without_bootstrap(self):
        with self.project_dir():
            result = self.runner.invoke(main, ["ready", "--json"])
            self.assertNotEqual(result.exit_code, 0)

            payload = json.loads(result.output)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["readiness_summary"]["status"], "needs_attention")
            self.assertTrue(payload["readiness_summary"]["blockers"])

    def test_ready_fix_bootstraps_core_files_and_context_index(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["ready", "--fix", "--json"])
            self.assertEqual(result.exit_code, 0, result.output)

            payload = json.loads(result.output)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["fix_requested"])
            self.assertTrue(any(item["name"] == "bootstrap" for item in payload["fixes"]))
            self.assertTrue(any(item["name"] == "context-index" for item in payload["fixes"]))
            self.assertTrue((cwd / "AGENTS.md").exists())
            self.assertTrue((cwd / ".agent" / "project_profile.yaml").exists())
            self.assertTrue((cwd / ".agent" / "context" / "project-context.md").exists())
            self.assertTrue((cwd / ".agent" / "STATE.md").exists())
            self.assertTrue((cwd / ".agent" / "context" / "index.json").exists())

    def test_ready_ci_emit_github_writes_deterministic_workflow_file(self):
        with self.project_dir() as cwd:
            first = self.runner.invoke(main, ["ready", "ci", "--emit", "github"])
            self.assertEqual(first.exit_code, 0, first.output)

            workflow_path = cwd / READY_WORKFLOW_PATH
            self.assertTrue(workflow_path.exists())
            content = workflow_path.read_text(encoding="utf-8")
            self.assertIn("Managed by `skillsmith ready ci --emit github`", content)
            self.assertIn("name: Skillsmith Ready", content)
            self.assertIn("python -m skillsmith ready", content)
            self.assertIn("python -m skillsmith report --artifact-dir .agent/reports/readiness", content)
            self.assertIn("uses: actions/upload-artifact@v4", content)
            self.assertIn("skillsmith-readiness", content)

            second = self.runner.invoke(main, ["ready", "ci", "--emit", "github"])
            self.assertEqual(second.exit_code, 0, second.output)
            self.assertEqual(content, workflow_path.read_text(encoding="utf-8"))

    def test_ready_ci_emit_github_refuses_to_overwrite_unmanaged_workflow(self):
        with self.project_dir() as cwd:
            workflow_path = cwd / READY_WORKFLOW_PATH
            workflow_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_path.write_text("name: Custom Workflow\n", encoding="utf-8")

            result = self.runner.invoke(main, ["ready", "ci", "--emit", "github", "--json"])
            self.assertNotEqual(result.exit_code, 0)

            payload = json.loads(result.output)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["status"], "refused")
            self.assertFalse(payload["managed"])
            self.assertIn("refusing to overwrite", payload["error"])
            self.assertEqual(workflow_path.read_text(encoding="utf-8"), "name: Custom Workflow\n")


if __name__ == "__main__":
    unittest.main()
