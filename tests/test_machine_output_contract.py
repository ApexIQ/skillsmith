import json
import os
import shutil
import time
import unittest
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


def _assert_type(testcase: unittest.TestCase, value, expected_type, label: str) -> None:
    testcase.assertIsInstance(value, expected_type, f"{label} must be {expected_type}")


def _normalize_compose_payload(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    normalized["trace_path"] = None
    workflow = normalized.get("workflow", {})
    if isinstance(workflow, dict):
        workflow.pop("context_trace", None)
    return normalized


class MachineOutputContractTests(unittest.TestCase):
    def test_schema_for_compose_recommend_doctor_json(self):
        runner = CliRunner()
        sandbox = ROOT / ".test-machine-output"
        sandbox.mkdir(parents=True, exist_ok=True)
        project = sandbox / f"schema-{int(time.time() * 1000)}"
        project.mkdir(parents=True, exist_ok=False)
        previous = Path.cwd()
        try:
            os.chdir(project)
            init_result = runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            compose_result = runner.invoke(main, ["compose", "build a project summary", "--json"])
            self.assertEqual(compose_result.exit_code, 0, compose_result.output)
            compose_payload = json.loads(compose_result.output)
            _assert_type(self, compose_payload, dict, "compose payload")
            for key in ("ok", "cwd", "goal", "workflow", "trace_path"):
                self.assertIn(key, compose_payload)
            _assert_type(self, compose_payload["ok"], bool, "compose.ok")
            _assert_type(self, compose_payload["cwd"], str, "compose.cwd")
            _assert_type(self, compose_payload["goal"], str, "compose.goal")
            _assert_type(self, compose_payload["workflow"], dict, "compose.workflow")
            self.assertTrue(isinstance(compose_payload["trace_path"], str) or compose_payload["trace_path"] is None)

            recommend_result = runner.invoke(main, ["recommend", "--json"])
            self.assertEqual(recommend_result.exit_code, 0, recommend_result.output)
            recommend_payload = json.loads(recommend_result.output)
            for key in ("profile_source", "profile", "limit", "count", "recommendations"):
                self.assertIn(key, recommend_payload)
            _assert_type(self, recommend_payload["profile_source"], str, "recommend.profile_source")
            _assert_type(self, recommend_payload["profile"], dict, "recommend.profile")
            _assert_type(self, recommend_payload["limit"], int, "recommend.limit")
            _assert_type(self, recommend_payload["count"], int, "recommend.count")
            _assert_type(self, recommend_payload["recommendations"], list, "recommend.recommendations")

            doctor_result = runner.invoke(main, ["doctor", "--json"])
            self.assertEqual(doctor_result.exit_code, 0, doctor_result.output)
            doctor_payload = json.loads(doctor_result.output)
            for key in ("ok", "cwd", "checks", "missing", "stale", "strict_failed"):
                self.assertIn(key, doctor_payload)
            _assert_type(self, doctor_payload["ok"], bool, "doctor.ok")
            _assert_type(self, doctor_payload["cwd"], str, "doctor.cwd")
            _assert_type(self, doctor_payload["checks"], list, "doctor.checks")
            _assert_type(self, doctor_payload["missing"], list, "doctor.missing")
            _assert_type(self, doctor_payload["stale"], list, "doctor.stale")
            _assert_type(self, doctor_payload["strict_failed"], bool, "doctor.strict_failed")
        finally:
            os.chdir(previous)
            shutil.rmtree(project, ignore_errors=True)

    def test_deterministic_json_outputs_across_three_runs(self):
        runner = CliRunner()
        sandbox = ROOT / ".test-machine-output"
        sandbox.mkdir(parents=True, exist_ok=True)
        project = sandbox / f"determinism-{int(time.time() * 1000)}"
        project.mkdir(parents=True, exist_ok=False)
        previous = Path.cwd()
        try:
            os.chdir(project)
            init_result = runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            compose_runs = []
            recommend_runs = []
            doctor_runs = []
            for _ in range(3):
                compose_result = runner.invoke(main, ["compose", "build a project summary", "--json", "--no-feedback"])
                self.assertEqual(compose_result.exit_code, 0, compose_result.output)
                compose_runs.append(_normalize_compose_payload(json.loads(compose_result.output)))

                recommend_result = runner.invoke(main, ["recommend", "--json"])
                self.assertEqual(recommend_result.exit_code, 0, recommend_result.output)
                recommend_runs.append(json.loads(recommend_result.output))

                doctor_result = runner.invoke(main, ["doctor", "--json"])
                self.assertEqual(doctor_result.exit_code, 0, doctor_result.output)
                doctor_runs.append(json.loads(doctor_result.output))

            first_compose = compose_runs[0]
            first_recommend = recommend_runs[0]
            first_doctor = doctor_runs[0]
            for payload in compose_runs[1:]:
                self.assertEqual(payload, first_compose)
            for payload in recommend_runs[1:]:
                self.assertEqual(payload, first_recommend)
            for payload in doctor_runs[1:]:
                self.assertEqual(payload, first_doctor)
        finally:
            os.chdir(previous)
            shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
