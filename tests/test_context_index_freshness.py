from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class ContextIndexFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @contextmanager
    def project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            previous = Path.cwd()
            os.chdir(cwd)
            try:
                yield cwd
            finally:
                os.chdir(previous)

    def _write_core_files(self, cwd: Path) -> None:
        (cwd / "AGENTS.md").write_text("agent rules", encoding="utf-8")
        (cwd / ".agent" / "project_profile.yaml").parent.mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "project_profile.yaml").write_text(
            "idea: freshness demo\nproject_stage: greenfield\napp_type: application\n",
            encoding="utf-8",
        )
        (cwd / ".agent" / "context").mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "context" / "project-context.md").write_text("# Project Context\nfreshness demo\n", encoding="utf-8")
        (cwd / "skills.lock.json").write_text(json.dumps({"version": 1, "skills": []}), encoding="utf-8")

    def _set_ages(self, cwd: Path, age_hours: float, paths: list[str]) -> None:
        timestamp = time.time() - (age_hours * 3600)
        for relative in paths:
            path = cwd / relative
            os.utime(path, (timestamp, timestamp))

    def test_context_index_freshness_reports_ok_for_fresh_project(self):
        with self.project_dir() as cwd:
            self._write_core_files(cwd)
            build_result = self.runner.invoke(main, ["context-index", "build"])
            self.assertEqual(build_result.exit_code, 0, build_result.output)

            result = self.runner.invoke(main, ["context-index", "freshness"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Context Freshness", result.output)
        self.assertIn("fresh, 0 stale, 0 missing", result.output)
        self.assertNotIn("Freshness check failed.", result.output)

    def test_context_index_freshness_json_reports_missing_index_and_nonzero_exit(self):
        with self.project_dir() as cwd:
            self._write_core_files(cwd)

            result = self.runner.invoke(main, ["context-index", "freshness", "--json"])

        self.assertEqual(result.exit_code, 1, result.output)
        payload = json.loads(result.output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["summary"]["missing"], 1)
        self.assertIn("skillsmith context-index build", payload["remediations"])
        self.assertEqual(payload["checks"][0]["state"], "missing")
        self.assertEqual(payload["checks"][0]["path"], ".agent/context/index.json")

    def test_context_index_freshness_flags_stale_files_and_lists_remediations(self):
        with self.project_dir() as cwd:
            self._write_core_files(cwd)
            build_result = self.runner.invoke(main, ["context-index", "build"])
            self.assertEqual(build_result.exit_code, 0, build_result.output)
            self._set_ages(
                cwd,
                age_hours=5,
                paths=[
                    "AGENTS.md",
                    ".agent/project_profile.yaml",
                    ".agent/context/project-context.md",
                    "skills.lock.json",
                    ".agent/context/index.json",
                ],
            )

            result = self.runner.invoke(main, ["context-index", "freshness", "--max-age-hours", "1"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Context Freshness", result.output)
        self.assertIn("stale", result.output)
        self.assertIn("skillsmith context-index build", result.output)
        self.assertIn("skillsmith sync", result.output)
        self.assertIn("skillsmith sync --auto-install", result.output)
        self.assertIn("skillsmith init --guided", result.output)


if __name__ == "__main__":
    unittest.main()
