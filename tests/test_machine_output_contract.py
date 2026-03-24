import json
import os
import shutil
import time
import unittest
import unittest.mock as mock
from types import SimpleNamespace
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


def _normalize_report_payload(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    normalized["provider_reliability"] = []
    return normalized


def _normalize_ready_payload(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    compose_payload = normalized.get("compose", {})
    if isinstance(compose_payload, dict):
        compose_payload["trace_path"] = None
    return normalized


def _normalize_start_payload(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    compose_payload = normalized.get("compose", {})
    if isinstance(compose_payload, dict):
        compose_payload["trace_path"] = None
    return normalized


class MachineOutputContractTests(unittest.TestCase):
    def test_schema_for_compose_recommend_doctor_ready_start_json(self):
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
            for key in (
                "ok",
                "cwd",
                "checks",
                "missing",
                "stale",
                "readiness_score",
                "readiness_checklist",
                "readiness_failing_checks",
                "readiness_passing_checks",
                "readiness_total_checks",
                "strict_failed",
            ):
                self.assertIn(key, doctor_payload)
            _assert_type(self, doctor_payload["ok"], bool, "doctor.ok")
            _assert_type(self, doctor_payload["cwd"], str, "doctor.cwd")
            _assert_type(self, doctor_payload["checks"], list, "doctor.checks")
            _assert_type(self, doctor_payload["missing"], list, "doctor.missing")
            _assert_type(self, doctor_payload["stale"], list, "doctor.stale")
            _assert_type(self, doctor_payload["readiness_score"], int, "doctor.readiness_score")
            _assert_type(self, doctor_payload["readiness_checklist"], list, "doctor.readiness_checklist")
            _assert_type(self, doctor_payload["readiness_failing_checks"], list, "doctor.readiness_failing_checks")
            _assert_type(self, doctor_payload["readiness_passing_checks"], int, "doctor.readiness_passing_checks")
            _assert_type(self, doctor_payload["readiness_total_checks"], int, "doctor.readiness_total_checks")
            _assert_type(self, doctor_payload["strict_failed"], bool, "doctor.strict_failed")
            self.assertEqual(doctor_payload["readiness_score"], 100)
            self.assertEqual(
                list(doctor_payload.keys()),
                [
                    "checks",
                    "cwd",
                    "missing",
                    "ok",
                    "readiness_checklist",
                    "readiness_failing_checks",
                    "readiness_passing_checks",
                    "readiness_score",
                    "readiness_total_checks",
                    "stale",
                    "strict_failed",
                ],
            )
            self.assertEqual(
                [item["name"] for item in doctor_payload["checks"]],
                ["AGENTS.md", ".agent/project_profile.yaml", ".agent/context/project-context.md", ".agent/STATE.md age <=24h"],
            )

            report_candidate = SimpleNamespace(name="python-packaging", source="local")
            with mock.patch(
                "skillsmith.commands.report.curated_pack_candidates", return_value=[report_candidate]
            ), mock.patch(
                "skillsmith.commands.report.curated_pack_label", return_value="library:python"
            ), mock.patch(
                "skillsmith.commands.report.explain_candidate",
                return_value={"reasons": ["starter pack match"], "matched_query": ["python"], "matched_profile": ["packaging"]},
            ):
                report_result = runner.invoke(main, ["report", "--json"])

            self.assertEqual(report_result.exit_code, 0, report_result.output)
            report_payload = json.loads(report_result.output)
            _assert_type(self, report_payload, dict, "report payload")
            for key in (
                "profile_source",
                "profile",
                "query",
                "starter_pack_label",
                "starter_pack",
                "policy",
                "trust_health",
                "provider_reliability",
                "eval_policy",
                "context_index_freshness",
                "registry_governance",
                "snapshot_files",
            ):
                self.assertIn(key, report_payload)
            _assert_type(self, report_payload["profile_source"], str, "report.profile_source")
            _assert_type(self, report_payload["profile"], dict, "report.profile")
            _assert_type(self, report_payload["query"], str, "report.query")
            _assert_type(self, report_payload["starter_pack_label"], str, "report.starter_pack_label")
            _assert_type(self, report_payload["starter_pack"], list, "report.starter_pack")
            _assert_type(self, report_payload["policy"], dict, "report.policy")
            _assert_type(self, report_payload["trust_health"], dict, "report.trust_health")
            _assert_type(self, report_payload["provider_reliability"], list, "report.provider_reliability")
            _assert_type(self, report_payload["eval_policy"], dict, "report.eval_policy")
            _assert_type(self, report_payload["context_index_freshness"], dict, "report.context_index_freshness")
            _assert_type(self, report_payload["registry_governance"], dict, "report.registry_governance")
            _assert_type(self, report_payload["snapshot_files"], dict, "report.snapshot_files")
            self.assertEqual(list(report_payload.keys()), sorted(report_payload.keys()))
            self.assertEqual(report_payload["starter_pack_label"], "library:python")
            self.assertEqual(len(report_payload["starter_pack"]), 1)
            self.assertEqual(report_payload["starter_pack"][0]["name"], "python-packaging")
            self.assertEqual(report_payload["starter_pack"][0]["source"], "local")
            self.assertEqual(report_payload["starter_pack"][0]["why"], ["starter pack match"])

            ready_result = runner.invoke(main, ["ready", "--json"])
            self.assertEqual(ready_result.exit_code, 0, ready_result.output)
            ready_payload = json.loads(ready_result.output)
            _assert_type(self, ready_payload, dict, "ready payload")
            for key in ("ok", "goal", "cwd", "guided_init_requested", "init", "doctor", "compose", "report", "readiness_summary"):
                self.assertIn(key, ready_payload)
            _assert_type(self, ready_payload["ok"], bool, "ready.ok")
            _assert_type(self, ready_payload["goal"], str, "ready.goal")
            _assert_type(self, ready_payload["cwd"], str, "ready.cwd")
            _assert_type(self, ready_payload["guided_init_requested"], bool, "ready.guided_init_requested")
            _assert_type(self, ready_payload["init"], dict, "ready.init")
            _assert_type(self, ready_payload["doctor"], dict, "ready.doctor")
            _assert_type(self, ready_payload["compose"], dict, "ready.compose")
            _assert_type(self, ready_payload["report"], dict, "ready.report")
            _assert_type(self, ready_payload["readiness_summary"], dict, "ready.readiness_summary")
            self.assertEqual(list(ready_payload.keys()), sorted(ready_payload.keys()))

            start_result = runner.invoke(main, ["start", "--json"])
            self.assertEqual(start_result.exit_code, 0, start_result.output)
            start_payload = json.loads(start_result.output)
            _assert_type(self, start_payload, dict, "start payload")
            for key in ("ok", "goal", "cwd", "guided_init_requested", "init", "doctor", "compose", "report", "readiness_summary"):
                self.assertIn(key, start_payload)
            _assert_type(self, start_payload["ok"], bool, "start.ok")
            _assert_type(self, start_payload["goal"], str, "start.goal")
            _assert_type(self, start_payload["cwd"], str, "start.cwd")
            _assert_type(self, start_payload["guided_init_requested"], bool, "start.guided_init_requested")
            _assert_type(self, start_payload["init"], dict, "start.init")
            _assert_type(self, start_payload["doctor"], dict, "start.doctor")
            _assert_type(self, start_payload["compose"], dict, "start.compose")
            _assert_type(self, start_payload["report"], dict, "start.report")
            _assert_type(self, start_payload["readiness_summary"], dict, "start.readiness_summary")
            self.assertEqual(list(start_payload.keys()), sorted(start_payload.keys()))
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
            report_runs = []
            ready_runs = []
            start_runs = []
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

                report_candidate = SimpleNamespace(name="python-packaging", source="local")
                with mock.patch(
                    "skillsmith.commands.report.curated_pack_candidates", return_value=[report_candidate]
                ), mock.patch(
                    "skillsmith.commands.report.curated_pack_label", return_value="library:python"
                ), mock.patch(
                    "skillsmith.commands.report.explain_candidate",
                    return_value={"reasons": ["starter pack match"], "matched_query": ["python"], "matched_profile": ["packaging"]},
                ):
                    report_result = runner.invoke(main, ["report", "--json"])
                self.assertEqual(report_result.exit_code, 0, report_result.output)
                report_runs.append(_normalize_report_payload(json.loads(report_result.output)))

                ready_result = runner.invoke(main, ["ready", "--json"])
                self.assertEqual(ready_result.exit_code, 0, ready_result.output)
                ready_runs.append(_normalize_ready_payload(json.loads(ready_result.output)))

                start_result = runner.invoke(main, ["start", "--json"])
                self.assertEqual(start_result.exit_code, 0, start_result.output)
                start_runs.append(_normalize_start_payload(json.loads(start_result.output)))

            first_compose = compose_runs[0]
            first_recommend = recommend_runs[0]
            first_doctor = doctor_runs[0]
            first_report = report_runs[0]
            first_ready = ready_runs[0]
            first_start = start_runs[0]
            for payload in compose_runs[1:]:
                self.assertEqual(payload, first_compose)
            for payload in recommend_runs[1:]:
                self.assertEqual(payload, first_recommend)
            for payload in doctor_runs[1:]:
                self.assertEqual(payload, first_doctor)
            for payload in report_runs[1:]:
                self.assertEqual(payload, first_report)
            for payload in ready_runs[1:]:
                self.assertEqual(payload, first_ready)
            for payload in start_runs[1:]:
                self.assertEqual(payload, first_start)
        finally:
            os.chdir(previous)
            shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
