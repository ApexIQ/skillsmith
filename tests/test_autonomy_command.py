import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class AutonomyCommandTests(unittest.TestCase):
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

    def test_autonomous_run_status_report_json_happy_path(self):
        fake_session = {
            "session_id": "run-1",
            "domain": "recommend",
            "status": "completed",
            "stop_reason": "max_iterations",
            "iterations": [{"iteration": 1, "decision": "keep", "score": 88.2}],
            "best_score": 88.2,
            "summary": {"score": 88.2, "trust_summary": {"state": "trusted", "score": 0.95}},
            "benchmark": {"name": "recommendation_tasks"},
            "intent": {
                "kind": "typed-intent",
                "type": "mutation-safe-refine",
                "goal": "Preserve runtime metadata across persistence",
            },
            "task_graph": {
                "kind": "task-graph",
                "root_task_id": "task-1",
                "nodes": [{"id": "task-1", "type": "plan"}],
            },
            "mutation_safety": {
                "snapshot": {"path": ".agent/snapshots/run-1", "exists": True},
                "rollback_policy": {"mode": "restore-on-failure"},
            },
            "run_manifest": {"session_id": "run-1", "iteration_count": 1, "status": "completed"},
            "lessons": [{"id": "lesson-1", "summary": "Restore the snapshot before retrying."}],
            "trust_summary": {"state": "trusted", "score": 0.95},
        }
        fake_summary = {
            "session_id": "run-1",
            "domain": "recommend",
            "status": "completed",
            "stop_reason": "max_iterations",
            "iterations": 1,
            "kept": 1,
            "discarded": 0,
            "crashed": 0,
            "best_score": 88.2,
            "final_score": 88.2,
            "benchmark_pack": "recommendation_tasks",
            "trust_summary": {"state": "trusted", "score": 0.95},
            "run_manifest": {"session_id": "run-1", "iteration_count": 1, "status": "completed"},
        }
        with self.project_dir(), mock.patch(
            "skillsmith.commands.autonomy.run_autonomy_session",
            return_value=fake_session,
        ), mock.patch(
            "skillsmith.commands.autonomy.load_latest_session",
            return_value=fake_session,
        ), mock.patch(
            "skillsmith.commands.autonomy.summarize_session",
            return_value=fake_summary,
        ):
            run_result = self.runner.invoke(main, ["autonomous", "run", "--json-output"])
            status_result = self.runner.invoke(main, ["autonomous", "status", "--json-output"])
            report_result = self.runner.invoke(main, ["autonomous", "report", "--json-output"])

        self.assertEqual(run_result.exit_code, 0, run_result.output)
        self.assertEqual(status_result.exit_code, 0, status_result.output)
        self.assertEqual(report_result.exit_code, 0, report_result.output)
        run_payload = json.loads(run_result.output)
        status_payload = json.loads(status_result.output)
        report_payload = json.loads(report_result.output)
        self.assertEqual(run_payload["summary"]["best_score"], 88.2)
        self.assertEqual(run_payload["session"]["intent"]["type"], "mutation-safe-refine")
        self.assertEqual(run_payload["session"]["run_manifest"]["status"], "completed")
        self.assertEqual(run_payload["session"]["lessons"][0]["id"], "lesson-1")
        self.assertEqual(status_payload["session"]["trust_summary"]["state"], "trusted")
        self.assertEqual(report_payload["summary"]["trust_summary"]["score"], 0.95)
        self.assertEqual(report_payload["summary"]["run_manifest"]["iteration_count"], 1)

    def test_autonomous_status_and_report_when_missing(self):
        with self.project_dir(), mock.patch(
            "skillsmith.commands.autonomy.load_latest_session",
            return_value=None,
        ):
            status_result = self.runner.invoke(main, ["autonomous", "status", "--json-output"])
            report_result = self.runner.invoke(main, ["autonomous", "report", "--json-output"])

        self.assertEqual(status_result.exit_code, 0, status_result.output)
        self.assertEqual(report_result.exit_code, 0, report_result.output)
        self.assertFalse(json.loads(status_result.output)["available"])
        self.assertFalse(json.loads(report_result.output)["available"])


if __name__ == "__main__":
    unittest.main()
