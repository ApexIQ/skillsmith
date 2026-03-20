import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class SkillsmithSuggestCommandTests(unittest.TestCase):
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

    def _write_lockfile(self, cwd: Path) -> None:
        (cwd / "skills.lock.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "schema_version": 2,
                    "skills": [
                        {
                            "name": "python-packaging",
                            "source": "local",
                            "version": "1.0.0",
                            "install_ref": "python-packaging",
                            "trust_score": 95,
                            "category": "general",
                            "tags": ["python"],
                            "installed_at": "2026-03-20T00:00:00Z",
                            "verification_timestamp": "2026-03-20T00:00:00Z",
                            "path": ".agent/skills/python-packaging",
                            "checksum": "abc123",
                            "metadata": {},
                            "provenance": {},
                            "recommendation": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_suggest_bootstraps_when_project_profile_is_missing(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["suggest"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Skillsmith Suggestions", result.output)
        self.assertIn("skillsmith init --guided", result.output)
        self.assertIn("profile or generated context is missing", result.output)

    def test_suggest_recommends_sync_and_recommend_when_generated_files_drift(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            (cwd / "AGENTS.md").write_text("local drift", encoding="utf-8")

            result = self.runner.invoke(main, ["suggest"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("skillsmith sync", result.output)
        self.assertIn("skillsmith recommend", result.output)
        self.assertIn("drifted from the saved profile", result.output)
        self.assertIn("no recorded skill set yet", result.output)

    def test_suggest_recommends_audit_and_compose_when_worktree_is_dirty_but_state_is_healthy(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            self._write_lockfile(cwd)

            with mock.patch(
                "skillsmith.commands.suggest._git_status_summary",
                return_value={
                    "available": True,
                    "branch": "main",
                    "dirty": True,
                    "dirty_count": 2,
                    "untracked_count": 1,
                    "modified_count": 1,
                    "status_lines": [" M AGENTS.md", "?? scratch.txt"],
                    "clean": False,
                },
            ):
                result = self.runner.invoke(main, ["suggest"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("skillsmith audit --strict", result.output)
        self.assertIn('skillsmith compose "build the next feature"', result.output)
        self.assertIn("git worktree has uncommitted changes", result.output)
        self.assertIn("the project instructions, context, and installed skills are in place", result.output)

