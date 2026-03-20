import copy
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

    def _write_latest_session(self, cwd: Path, session: dict) -> None:
        autonomy_root = cwd / ".agent" / "autonomy"
        session_path = autonomy_root / "runs" / f"{session['session_id']}.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(json.dumps(session, indent=2, sort_keys=True), encoding="utf-8")
        (autonomy_root / "latest.json").write_text(
            json.dumps(
                {
                    "kind": "latest-pointer",
                    "schema_version": 1,
                    "session_id": session["session_id"],
                    "session_path": session_path.as_posix(),
                    "status": session["status"],
                    "updated_at": session["updated_at"],
                    "summary": session.get("summary", {}),
                    "_base_dir": autonomy_root.as_posix(),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def _structured_session_payload(self) -> dict:
        intent = {
            "kind": "typed-intent",
            "type": "mutation-safe-refine",
            "goal": "Preserve runtime metadata across persistence",
            "constraints": ["deterministic", "minimal"],
        }
        task_graph = {
            "kind": "task-graph",
            "root_task_id": "task-1",
            "nodes": [
                {"id": "task-1", "type": "plan", "status": "done"},
                {"id": "task-2", "type": "verify", "status": "pending"},
            ],
            "edges": [{"from": "task-1", "to": "task-2", "relation": "follow-up"}],
        }
        mutation_safety = {
            "snapshot": {
                "path": ".agent/snapshots/autonomy-run-1",
                "exists": True,
            },
            "rollback_policy": {
                "mode": "restore-on-failure",
                "preserve_untracked": True,
            },
            "rolled_back": False,
        }
        run_manifest = {
            "session_id": "20260320T120000Z-typedmeta",
            "iteration_count": 1,
            "status": "completed",
            "stop_reason": "max_iterations",
            "intent_type": intent["type"],
            "task_graph_root": task_graph["root_task_id"],
        }
        lessons = [
            {
                "id": "lesson-1",
                "topic": "rollback",
                "summary": "Restore the snapshot before retrying.",
                "source": "iteration-1",
                "confidence": 0.9,
            }
        ]
        trust_summary = {
            "state": "trusted",
            "score": 0.92,
            "signals": ["signed-manifest", "clean-git"],
            "issues": [],
        }
        iteration = {
            "kind": "autonomy-iteration",
            "schema_version": 1,
            "session_id": "20260320T120000Z-typedmeta",
            "iteration": 1,
            "started_at": "2026-03-20T12:00:00Z",
            "finished_at": "2026-03-20T12:01:00Z",
            "elapsed_seconds": 60.0,
            "decision": "keep",
            "status": "kept",
            "strict_gate": {"passed": True, "returncode": 0},
            "benchmark": {
                "pack_name": "recommendation_tasks",
                "task_count": 1,
                "score": 91.5,
                "matched_expected_count": 1,
                "expected_count": 1,
                "task_results": [
                    {
                        "task_id": "t1",
                        "title": "Library",
                        "goal": "Validate metadata persistence",
                        "expected_skills": ["python-packaging"],
                        "candidate_count": 1,
                        "score": 91.5,
                    }
                ],
            },
            "score": 91.5,
            "score_gate": 60.0,
            "best_score": 91.5,
            "non_improving_streak": 0,
            "intent": intent,
            "task_graph": task_graph,
            "mutation_safety": mutation_safety,
            "run_manifest": run_manifest,
            "lessons": lessons,
            "trust_summary": trust_summary,
        }
        return {
            "kind": "autonomy-session",
            "schema_version": 1,
            "session_id": "20260320T120000Z-typedmeta",
            "domain": "recommend",
            "cwd": "C:/tmp/autonomy-contract",
            "started_at": "2026-03-20T12:00:00Z",
            "updated_at": "2026-03-20T12:01:00Z",
            "finished_at": "2026-03-20T12:02:00Z",
            "status": "completed",
            "stop_reason": "max_iterations",
            "final_decision": "keep",
            "score_gate": 60.0,
            "max_iterations": 3,
            "max_hours": 1.0,
            "max_non_improving": 2,
            "recommendation_limit": 5,
            "strict_test_command": ["uv", "run", "python", "-m", "unittest", "discover", "tests", "-v"],
            "strict_gate": True,
            "profile": {"app_type": "library", "languages": ["python"]},
            "benchmark": {"name": "recommendation_tasks", "task_count": 1, "tasks": [{"id": "t1", "title": "Library"}]},
            "preflight": self._clean_git(),
            "iterations": [iteration],
            "best_score": 91.5,
            "best_iteration": 1,
            "last_score": 91.5,
            "last_strict_gate": {"passed": True, "returncode": 0},
            "summary": {"score": 91.5, "matched_expected_count": 1, "expected_count": 1},
            "duration_seconds": 60.0,
            "intent": intent,
            "task_graph": task_graph,
            "mutation_safety": mutation_safety,
            "run_manifest": run_manifest,
            "lessons": lessons,
            "trust_summary": trust_summary,
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

    def test_latest_session_preserves_structured_runtime_metadata(self):
        with self.project_dir() as cwd:
            session = self._structured_session_payload()
            self._write_latest_session(cwd, session)

            latest = runtime.load_latest_session(cwd)
            before_summary = copy.deepcopy(latest)
            summary = runtime.summarize_session(latest)

        self.assertIsInstance(latest, dict)
        self.assertEqual(latest, before_summary)
        self.assertEqual(latest["intent"], latest["iterations"][0]["intent"])
        self.assertEqual(latest["task_graph"], latest["iterations"][0]["task_graph"])
        self.assertEqual(latest["mutation_safety"], latest["iterations"][0]["mutation_safety"])
        self.assertEqual(latest["run_manifest"], latest["iterations"][0]["run_manifest"])
        self.assertEqual(latest["lessons"], latest["iterations"][0]["lessons"])
        self.assertEqual(latest["trust_summary"], latest["iterations"][0]["trust_summary"])
        self.assertEqual(summary["iterations"], 1)
        self.assertEqual(summary["best_score"], 91.5)
        self.assertEqual(summary["final_score"], 91.5)
        self.assertEqual(summary["decision_counts"], {"keep": 1, "discard": 0, "crash": 0})

    def test_structured_lessons_and_manifest_contract_round_trip(self):
        with self.project_dir() as cwd:
            session = self._structured_session_payload()
            session["run_manifest"]["iteration_count"] = len(session["iterations"])
            session["run_manifest"]["status"] = session["status"]
            session["run_manifest"]["stop_reason"] = session["stop_reason"]
            session["iterations"][0]["run_manifest"] = dict(session["run_manifest"])
            self._write_latest_session(cwd, session)

            latest = runtime.load_latest_session(cwd)

        self.assertEqual(latest["run_manifest"]["session_id"], latest["session_id"])
        self.assertEqual(latest["run_manifest"]["iteration_count"], len(latest["iterations"]))
        self.assertEqual(latest["lessons"][0]["summary"], "Restore the snapshot before retrying.")
        self.assertEqual(latest["lessons"][0]["confidence"], 0.9)
        self.assertEqual(latest["trust_summary"]["state"], "trusted")


if __name__ == "__main__":
    unittest.main()
