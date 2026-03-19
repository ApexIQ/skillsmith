import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.commands import autonomy_runtime as runtime


class AutonomyRuntimeTests(unittest.TestCase):
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

    def _write_benchmark(self, cwd: Path) -> None:
        benchmark = cwd / ".agent" / "autonomy" / "benchmarks" / "recommendation_tasks.json"
        benchmark.parent.mkdir(parents=True, exist_ok=True)
        benchmark.write_text(
            json.dumps(
                {
                    "name": "recommendation_tasks",
                    "tasks": [
                        {"id": "t1", "title": "Library", "expected_skills": ["python-packaging"]},
                        {"id": "t2", "title": "Debug", "expected_skills": ["debugging"]},
                    ],
                }
            ),
            encoding="utf-8",
        )

    def _clean_git(self):
        return {
            "state": "clean",
            "clean": True,
            "reason": "",
            "dirty_paths": [],
            "branch": "main",
            "commit": "abc123",
            "status": "",
        }

    def test_stops_on_max_iterations(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.autonomy_runtime._git_preflight",
            return_value=self._clean_git(),
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime._run_strict_gate",
            return_value={"passed": True, "returncode": 0},
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime.explain_recommendations_for_profile",
            return_value=[],
        ):
            self._write_benchmark(cwd)
            session = runtime.run_autonomy_session(
                cwd=cwd,
                max_iterations=1,
                max_hours=1.0,
                max_non_improving=10,
                strict_gate=False,
            )

        self.assertEqual(session["stop_reason"], "max_iterations")
        self.assertEqual(len(session["iterations"]), 1)
        self.assertGreaterEqual(
            len(session["iterations"]),
            1,
        )

    def test_stops_on_early_non_improving(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.autonomy_runtime._git_preflight",
            return_value=self._clean_git(),
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime._run_strict_gate",
            return_value={"passed": True, "returncode": 0},
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime.explain_recommendations_for_profile",
            return_value=[],
        ):
            self._write_benchmark(cwd)
            session = runtime.run_autonomy_session(
                cwd=cwd,
                max_iterations=10,
                max_hours=1.0,
                max_non_improving=1,
                score_gate=99.0,
                strict_gate=False,
            )

        self.assertEqual(session["stop_reason"], "max_non_improving")
        self.assertGreaterEqual(len(session["iterations"]), 1)

    def test_crash_when_strict_gate_fails(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.autonomy_runtime._git_preflight",
            return_value=self._clean_git(),
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime._run_strict_gate",
            return_value={"passed": False, "returncode": 1, "stderr": "boom"},
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime.explain_recommendations_for_profile",
            return_value=[],
        ):
            self._write_benchmark(cwd)
            session = runtime.run_autonomy_session(
                cwd=cwd,
                max_iterations=3,
                max_hours=1.0,
                max_non_improving=3,
                strict_gate=True,
            )

        self.assertEqual(session["stop_reason"], "strict_gate_failed")
        self.assertEqual(session["status"], "crashed")
        self.assertEqual(session["iterations"][0]["decision"], "crash")

    def test_latest_session_and_summary(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.autonomy_runtime._git_preflight",
            return_value=self._clean_git(),
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime._run_strict_gate",
            return_value={"passed": True, "returncode": 0},
        ), mock.patch(
            "skillsmith.commands.autonomy_runtime.explain_recommendations_for_profile",
            return_value=[],
        ):
            self._write_benchmark(cwd)
            session = runtime.run_autonomy_session(
                cwd=cwd,
                max_iterations=1,
                max_hours=1.0,
                max_non_improving=10,
                strict_gate=False,
            )
            latest = runtime.load_latest_session(cwd)
            summary = runtime.summarize_session(latest)

        self.assertIsInstance(latest, dict)
        self.assertEqual(latest["session_id"], session["session_id"])
        self.assertEqual(summary["iterations"], 1)
        self.assertIn(summary["status"], {"completed", "crashed", "blocked"})


if __name__ == "__main__":
    unittest.main()
