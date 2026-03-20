import os
import shutil
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

import skillsmith


class PublicApiTests(unittest.TestCase):
    def setUp(self):
        self._cwd = None

    def tearDown(self):
        if self._cwd is not None:
            os.chdir(self._cwd)
            self._cwd = None

    @contextmanager
    def temp_project(self):
        sandbox = ROOT / ".test-tmp-public-api"
        sandbox.mkdir(parents=True, exist_ok=True)
        tmp = sandbox / f"public-api-{int(time.time() * 1000)}"
        tmp.mkdir(parents=True, exist_ok=False)
        previous = Path.cwd()
        os.chdir(tmp)
        self._cwd = previous
        try:
            yield tmp
        finally:
            os.chdir(previous)
            self._cwd = None
            shutil.rmtree(tmp, ignore_errors=True)

    def test_public_api_exports_are_callable(self):
        for name in ("init_project", "compose_workflow", "doctor_summary"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(skillsmith, name), f"skillsmith.{name} is missing")
                self.assertTrue(callable(getattr(skillsmith, name)), f"skillsmith.{name} is not callable")

    def test_init_project_smoke_writes_bootstrap_artifacts(self):
        with self.temp_project() as cwd:
            result = skillsmith.init_project(".")

            self.assertIsInstance(result, dict)
            self.assertIn("ok", result)
            self.assertIn("cwd", result)
            self.assertIn("artifacts", result)
            self.assertTrue(result["ok"])

            self.assertTrue((cwd / "AGENTS.md").exists(), "AGENTS.md was not created")
            self.assertTrue((cwd / ".agent" / "project_profile.yaml").exists(), "project profile was not created")
            self.assertTrue((cwd / ".agent" / "context" / "project-context.md").exists(), "project context was not created")

    def test_compose_workflow_smoke_returns_workflow_schema(self):
        with self.temp_project():
            skillsmith.init_project(".")

            result = skillsmith.compose_workflow("build a project summary")

            self.assertIsInstance(result, dict)
            self.assertIn("ok", result)
            self.assertTrue(result["ok"])
            self.assertIn("goal", result)
            self.assertIn("workflow", result)
            self.assertEqual(result["goal"], "build a project summary")
            self.assertIsInstance(result["workflow"], dict)
            self.assertIsInstance(result["workflow"].get("steps", []), list)
            if "stages" in result["workflow"]:
                self.assertIsInstance(result["workflow"]["stages"], (list, dict))

    def test_doctor_summary_smoke_reports_checks_and_ok_for_fresh_project(self):
        with self.temp_project():
            skillsmith.init_project(".")

            result = skillsmith.doctor_summary(".")

            self.assertIsInstance(result, dict)
            self.assertIn("ok", result)
            self.assertIn("checks", result)
            self.assertIn("strict_failed", result)
            self.assertTrue(result["ok"])
            self.assertFalse(result["strict_failed"])
            self.assertTrue(result["checks"])

    def test_doctor_summary_strict_marks_missing_agents_as_failed(self):
        with self.temp_project() as cwd:
            skillsmith.init_project(".")
            (cwd / "AGENTS.md").unlink()

            result = skillsmith.doctor_summary(".", strict=True)

            self.assertIsInstance(result, dict)
            self.assertIn("strict_failed", result)
            self.assertTrue(result["strict_failed"])


if __name__ == "__main__":
    unittest.main()
