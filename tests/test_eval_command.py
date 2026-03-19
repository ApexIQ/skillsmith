import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


class EvalCommandTests(unittest.TestCase):
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

    def _write_runs(self, path: Path, runs: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"runs": runs}), encoding="utf-8")

    def _write_policy(
        self,
        path: Path,
        *,
        pack: str | None = None,
        thresholds: dict | None = None,
        budget_profiles: dict | None = None,
        slo_budgets: dict | None = None,
        selected_budget_profile: str | None = None,
    ) -> None:
        payload: dict[str, object] = {}
        if pack is not None:
            payload["pack"] = pack
        if thresholds is not None:
            payload["thresholds"] = thresholds
        if budget_profiles is not None:
            payload["budget_profiles"] = budget_profiles
        if slo_budgets is not None:
            payload["slo_budgets"] = slo_budgets
        if selected_budget_profile is not None:
            payload["selected_budget_profile"] = selected_budget_profile
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_project_profile(self, path: Path, *, app_type: str) -> None:
        payload = {
            "idea": "Eval project",
            "project_stage": "existing",
            "app_type": app_type,
            "languages": ["python"],
            "frameworks": ["pytest"],
            "package_manager": "uv",
            "deployment_target": "not-specified",
            "priorities": ["verification"],
            "target_tools": ["codex"],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_artifact(self, path: Path, *, generated_at: str, summary: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 2,
            "generated_at": generated_at,
            "summary": summary,
            "trend": {"available": False},
            "runs": [],
            "policy": {},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(path, (1, 1))

    def test_eval_lists_builtin_packs(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["eval", "packs"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Eval Packs", result.output)
            self.assertIn("ci", result.output)
            self.assertIn("smoke", result.output)
            self.assertIn("library", result.output)
            self.assertIn("built-in", result.output)
            self.assertIn("yes", result.output)

    def test_eval_writes_artifact_and_computes_tacr(self):
        with self.project_dir() as cwd:
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "r1", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 1000, "cost_usd": 0.2, "interventions": 0},
                    {"id": "r2", "tests_passed": True, "policy_passed": False, "rollback_required": False, "latency_ms": 2000, "cost_usd": 0.4, "interventions": 1},
                    {"id": "r3", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 3000, "cost_usd": 0.6, "interventions": 2},
                ],
            )

            result = self.runner.invoke(main, ["eval"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Eval", result.output)
            self.assertIn("66.67%", result.output)
            latest = cwd / ".agent" / "evals" / "results" / "latest.json"
            self.assertTrue(latest.exists())
            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_runs"], 3)
            self.assertEqual(payload["summary"]["successful_runs"], 2)
            self.assertIn("trend", payload)

    def test_eval_resolves_budget_profile_for_app_type_and_allows_overrides(self):
        with self.project_dir() as cwd:
            self._write_project_profile(cwd / ".agent" / "project_profile.yaml", app_type="library")
            self._write_policy(
                cwd / ".agent" / "evals" / "policy.json",
                pack="ci",
                thresholds={
                    "min_tacr_delta": 0,
                    "max_latency_increase_ms": 0,
                    "max_cost_increase_usd": 0,
                },
                budget_profiles={
                    "library": {
                        "thresholds": {
                            "min_tacr_delta": 10,
                            "max_latency_increase_ms": 0,
                            "max_cost_increase_usd": 0,
                        }
                    },
                    "default": {
                        "thresholds": {
                            "min_tacr_delta": 0,
                            "max_latency_increase_ms": 0,
                            "max_cost_increase_usd": 0,
                        }
                    },
                },
            )
            results_dir = cwd / ".agent" / "evals" / "results"
            self._write_artifact(
                results_dir / "eval-2026-03-18T00-00-00Z.json",
                generated_at="2026-03-18T00:00:00Z",
                summary={
                    "total_runs": 2,
                    "successful_runs": 1,
                    "tacr": 50.0,
                    "avg_latency_ms": 100,
                    "avg_cost_usd": 0.1,
                    "total_interventions": 1,
                },
            )
            self._write_runs(
                cwd / ".agent" / "evals" / "runs.json",
                [
                    {"id": "run1", "task_id": "library_prepare", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 100, "cost_usd": 0.1},
                    {"id": "run2", "task_id": "library_execute", "tests_passed": False, "policy_passed": False, "rollback_required": True, "latency_ms": 100, "cost_usd": 0.1},
                ],
            )

            result = self.runner.invoke(main, ["eval"], env={"CI": "true"})

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("[GATE][FAIL]", result.output)
            latest = json.loads((results_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["policy"]["selected_budget_profile"], "library")
            self.assertEqual(latest["policy"]["selected_budget_profile_thresholds"]["min_tacr_delta"], 10.0)
            self.assertEqual(latest["policy"]["effective_thresholds"]["min_tacr_delta"], 10.0)
            self.assertEqual(latest["policy"]["effective_thresholds"]["max_latency_increase_ms"], 0.0)
            self.assertEqual(latest["policy"]["effective_thresholds"]["max_cost_increase_usd"], 0.0)
            self.assertEqual(latest["policy"]["app_type"], "library")

            override = self.runner.invoke(
                main,
                ["eval", "--min-tacr-delta", "0"],
                env={"CI": "true"},
            )
            self.assertEqual(override.exit_code, 0, override.output)
            override_latest = json.loads((results_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(override_latest["policy"]["effective_thresholds"]["min_tacr_delta"], 0.0)
            self.assertIn("[GATE][PASS]", override.output)

    def test_eval_resolves_slo_budget_and_falls_back_to_default(self):
        with self.project_dir() as cwd:
            self._write_project_profile(cwd / ".agent" / "project_profile.yaml", app_type="library")
            self._write_policy(
                cwd / ".agent" / "evals" / "policy.json",
                pack="ci",
                thresholds={
                    "min_tacr_delta": 0,
                    "max_latency_increase_ms": 0,
                    "max_cost_increase_usd": 0,
                },
                budget_profiles={
                    "release": {
                        "slo_budget": "release-tight",
                        "thresholds": {
                            "min_tacr_delta": 10,
                            "max_latency_increase_ms": 0,
                            "max_cost_increase_usd": 0,
                        },
                    },
                    "default": {
                        "slo_budget": "default",
                        "thresholds": {
                            "min_tacr_delta": 0,
                            "max_latency_increase_ms": 0,
                            "max_cost_increase_usd": 0,
                        },
                    },
                },
                slo_budgets={
                    "default": {
                        "thresholds": {
                            "tacr_floor": 75,
                            "delta_tacr_floor": 0,
                            "interventions_threshold": 3,
                            "latency_increase_threshold_ms": 0,
                            "cost_increase_threshold_usd": 0,
                        },
                        "caps": {
                            "verification_pass_floor": 1,
                            "verification_pass_cap": 4,
                            "reflection_retry_cap": 3,
                            "allow_mode_switch": True,
                        },
                    },
                    "release-tight": {
                        "thresholds": {
                            "tacr_floor": 90,
                            "delta_tacr_floor": 0,
                            "interventions_threshold": 1,
                            "latency_increase_threshold_ms": 0,
                            "cost_increase_threshold_usd": 0,
                        },
                        "caps": {
                            "verification_pass_floor": 1,
                            "verification_pass_cap": 2,
                            "reflection_retry_cap": 1,
                            "allow_mode_switch": False,
                        },
                    },
                },
                selected_budget_profile="release",
            )
            self._write_runs(
                cwd / ".agent" / "evals" / "runs.json",
                [
                    {"id": "run1", "task_id": "library_prepare", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 100, "cost_usd": 0.1},
                ],
            )

            result = self.runner.invoke(main, ["eval"])

            self.assertEqual(result.exit_code, 0, result.output)
            latest = json.loads((cwd / ".agent" / "evals" / "results" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["policy"]["selected_slo_budget"], "release-tight")
            self.assertEqual(latest["policy"]["selected_slo_budget_selector"], "budget_profiles.release.slo_budget")
            self.assertEqual(latest["policy"]["resolved_slo_budget"]["name"], "release-tight")
            self.assertEqual(latest["policy"]["resolved_slo_budget"]["thresholds"]["tacr_floor"], 90.0)
            self.assertFalse(latest["policy"]["resolved_slo_budget"]["caps"]["allow_mode_switch"])

            self._write_project_profile(cwd / ".agent" / "project_profile.yaml", app_type="unknown")
            self._write_policy(
                cwd / ".agent" / "evals" / "policy.json",
                pack="ci",
                thresholds={
                    "min_tacr_delta": 0,
                    "max_latency_increase_ms": 0,
                    "max_cost_increase_usd": 0,
                },
                budget_profiles={
                    "default": {
                        "slo_budget": "default",
                        "thresholds": {
                            "min_tacr_delta": 0,
                            "max_latency_increase_ms": 0,
                            "max_cost_increase_usd": 0,
                        },
                    }
                },
                slo_budgets={
                    "default": {
                        "thresholds": {
                            "tacr_floor": 75,
                            "delta_tacr_floor": 0,
                            "interventions_threshold": 3,
                            "latency_increase_threshold_ms": 0,
                            "cost_increase_threshold_usd": 0,
                        },
                        "caps": {
                            "verification_pass_floor": 1,
                            "verification_pass_cap": 4,
                            "reflection_retry_cap": 3,
                            "allow_mode_switch": True,
                        },
                    }
                },
            )

            fallback_result = self.runner.invoke(main, ["eval"])

            self.assertEqual(fallback_result.exit_code, 0, fallback_result.output)
            fallback_latest = json.loads((cwd / ".agent" / "evals" / "results" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(fallback_latest["policy"]["selected_slo_budget"], "default")
            self.assertEqual(fallback_latest["policy"]["resolved_slo_budget"]["name"], "default")
            self.assertEqual(fallback_latest["policy"]["resolved_slo_budget"]["caps"]["verification_pass_cap"], 4)

    def test_eval_ci_policy_auto_fails_without_opt_out(self):
        with self.project_dir() as cwd:
            self._write_policy(
                cwd / ".agent" / "evals" / "policy.json",
                pack="smoke",
                thresholds={
                    "min_tacr_delta": 0,
                    "max_latency_increase_ms": 0,
                    "max_cost_increase_usd": 0,
                },
            )
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "baseline-1", "task_id": "smoke_prepare", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 100, "cost_usd": 0.05},
                    {"id": "baseline-2", "task_id": "smoke_execute", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 100, "cost_usd": 0.05},
                ],
            )
            first = self.runner.invoke(main, ["eval"])
            self.assertEqual(first.exit_code, 0, first.output)

            self._write_runs(
                runs_path,
                [
                    {"id": "candidate-1", "task_id": "smoke_prepare", "tests_passed": False, "policy_passed": True, "rollback_required": True, "latency_ms": 250, "cost_usd": 0.2},
                    {"id": "candidate-2", "task_id": "smoke_execute", "tests_passed": False, "policy_passed": False, "rollback_required": False, "latency_ms": 250, "cost_usd": 0.2},
                ],
            )
            result = self.runner.invoke(main, ["eval"], env={"CI": "true"})

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("[GATE][FAIL]", result.output)
            latest = json.loads((cwd / ".agent" / "evals" / "results" / "latest.json").read_text(encoding="utf-8"))
            self.assertTrue(latest["policy"]["ci_enforced"])
            self.assertFalse(latest["policy"]["opt_out"])
            self.assertEqual(latest["policy"]["effective_thresholds"]["min_tacr_delta"], 0.0)
            self.assertEqual(latest["policy"]["effective_thresholds"]["max_latency_increase_ms"], 0.0)
            self.assertEqual(latest["policy"]["effective_thresholds"]["max_cost_increase_usd"], 0.0)
            self.assertLess(latest["trend"]["delta_tacr"], 0)

    def test_eval_supports_benchmark_pack_runs_mapping(self):
        with self.project_dir() as cwd:
            pack_path = cwd / ".agent" / "evals" / "packs" / "smoke.json"
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            pack_path.write_text(
                json.dumps(
                    {
                        "name": "smoke",
                        "runs_file": "runs-smoke.json",
                        "tasks": [
                            {"id": "task_a", "title": "A"},
                            {"id": "task_b", "title": "B"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self._write_runs(
                cwd / ".agent" / "evals" / "runs-smoke.json",
                [
                    {"id": "run1", "task_id": "task_a", "tests_passed": True, "policy_passed": True, "rollback_required": False},
                    {"id": "run2", "task_id": "task_a", "tests_passed": True, "policy_passed": False, "rollback_required": False},
                ],
            )

            result = self.runner.invoke(main, ["eval", "--pack", "smoke"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pack: smoke", result.output)
            latest = json.loads((cwd / ".agent" / "evals" / "results" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["benchmark_pack"]["name"], "smoke")
            self.assertEqual(latest["summary"]["benchmark_pack"]["total_tasks"], 2)
            self.assertEqual(latest["summary"]["benchmark_pack"]["tasks_with_runs"], 1)
            self.assertIn("runs-smoke.json", latest["source"])

    def test_eval_outputs_trend_deltas_against_previous_artifact(self):
        with self.project_dir() as cwd:
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "r1", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 1000, "cost_usd": 0.1},
                    {"id": "r2", "tests_passed": False, "policy_passed": True, "rollback_required": True, "latency_ms": 1000, "cost_usd": 0.1},
                ],
            )
            first = self.runner.invoke(main, ["eval"])
            self.assertEqual(first.exit_code, 0, first.output)

            self._write_runs(
                runs_path,
                [
                    {"id": "r3", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.05},
                    {"id": "r4", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.05},
                ],
            )
            second = self.runner.invoke(main, ["eval"])
            self.assertEqual(second.exit_code, 0, second.output)
            self.assertIn("Trend vs", second.output)
            self.assertIn("Delta TACR", second.output)

            latest = json.loads((cwd / ".agent" / "evals" / "results" / "latest.json").read_text(encoding="utf-8"))
            self.assertTrue(latest["trend"]["available"])
            self.assertGreater(latest["trend"]["delta_tacr"], 0)
            self.assertLess(latest["trend"]["delta_avg_latency_ms"], 0)
            self.assertLess(latest["trend"]["delta_avg_cost_usd"], 0)

    def test_eval_dashboard_summarizes_rolling_artifacts(self):
        with self.project_dir() as cwd:
            results_dir = cwd / ".agent" / "evals" / "results"
            self._write_artifact(
                results_dir / "eval-2026-03-17T00-00-00Z.json",
                generated_at="2026-03-17T00:00:00Z",
                summary={
                    "total_runs": 2,
                    "successful_runs": 1,
                    "tacr": 50.0,
                    "avg_latency_ms": 100,
                    "avg_cost_usd": 0.1000,
                    "total_interventions": 1,
                },
            )
            self._write_artifact(
                results_dir / "eval-2026-03-18T00-00-00Z.json",
                generated_at="2026-03-18T00:00:00Z",
                summary={
                    "total_runs": 2,
                    "successful_runs": 2,
                    "tacr": 75.0,
                    "avg_latency_ms": 80,
                    "avg_cost_usd": 0.0800,
                    "total_interventions": 2,
                },
            )
            self._write_artifact(
                results_dir / "eval-2026-03-19T00-00-00Z.json",
                generated_at="2026-03-19T00:00:00Z",
                summary={
                    "total_runs": 2,
                    "successful_runs": 2,
                    "tacr": 100.0,
                    "avg_latency_ms": 60,
                    "avg_cost_usd": 0.0600,
                    "total_interventions": 3,
                },
            )

            result = self.runner.invoke(main, ["eval", "dashboard"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Eval Dashboard", result.output)
            self.assertIn("Rolling TACR", result.output)
            self.assertIn("eval-2026-03-19T00-00-00Z.json", result.output)
            self.assertIn("75.00%", result.output)
            self.assertIn("80.00", result.output)
            self.assertIn("0.0800", result.output)
            self.assertIn("2.00", result.output)

    def test_eval_gate_passes_with_thresholds_against_previous_artifact(self):
        with self.project_dir() as cwd:
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "baseline-1", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 1000, "cost_usd": 0.3},
                    {"id": "baseline-2", "tests_passed": False, "policy_passed": True, "rollback_required": False, "latency_ms": 1000, "cost_usd": 0.3},
                ],
            )
            first = self.runner.invoke(main, ["eval"])
            self.assertEqual(first.exit_code, 0, first.output)

            self._write_runs(
                runs_path,
                [
                    {"id": "candidate-1", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.1},
                    {"id": "candidate-2", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.1},
                ],
            )
            result = self.runner.invoke(
                main,
                [
                    "eval",
                    "--min-tacr-delta",
                    "0",
                    "--max-latency-increase-ms",
                    "0",
                    "--max-cost-increase-usd",
                    "0",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("[GATE][PASS]", result.output)
            self.assertIn("Regression gates vs", result.output)

    def test_eval_gate_fails_with_thresholds_against_previous_artifact(self):
        with self.project_dir() as cwd:
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "baseline-1", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.1},
                    {"id": "baseline-2", "tests_passed": True, "policy_passed": True, "rollback_required": False, "latency_ms": 500, "cost_usd": 0.1},
                ],
            )
            first = self.runner.invoke(main, ["eval"])
            self.assertEqual(first.exit_code, 0, first.output)

            self._write_runs(
                runs_path,
                [
                    {"id": "candidate-1", "tests_passed": False, "policy_passed": False, "rollback_required": True, "latency_ms": 1500, "cost_usd": 0.4},
                    {"id": "candidate-2", "tests_passed": False, "policy_passed": True, "rollback_required": False, "latency_ms": 1500, "cost_usd": 0.4},
                ],
            )
            result = self.runner.invoke(
                main,
                [
                    "eval",
                    "--min-tacr-delta",
                    "0",
                    "--max-latency-increase-ms",
                    "0",
                    "--max-cost-increase-usd",
                    "0",
                ],
            )

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("[GATE][FAIL]", result.output)
            self.assertIn("TACR delta", result.output)
            self.assertTrue((cwd / ".agent" / "evals" / "results" / "latest.json").exists())

    def test_eval_run_subcommand_matches_default_behavior(self):
        with self.project_dir() as cwd:
            runs_path = cwd / ".agent" / "evals" / "runs.json"
            self._write_runs(
                runs_path,
                [
                    {"id": "r1", "tests_passed": True, "policy_passed": True, "rollback_required": False},
                ],
            )
            result = self.runner.invoke(main, ["eval", "run"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Eval", result.output)
            latest = cwd / ".agent" / "evals" / "results" / "latest.json"
            self.assertTrue(latest.exists())

    def test_eval_compare_subcommand_reports_deltas(self):
        with self.project_dir() as cwd:
            eval_dir = cwd / ".agent" / "evals" / "results"
            eval_dir.mkdir(parents=True, exist_ok=True)
            baseline = eval_dir / "baseline.json"
            candidate = eval_dir / "candidate.json"
            baseline.write_text(
                json.dumps({"summary": {"tacr": 50.0, "avg_latency_ms": 1000, "avg_cost_usd": 0.2}}),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps({"summary": {"tacr": 75.0, "avg_latency_ms": 800, "avg_cost_usd": 0.15}}),
                encoding="utf-8",
            )
            result = self.runner.invoke(
                main,
                ["eval", "compare", "--baseline", str(baseline), "--candidate", str(candidate)],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Eval Compare", result.output)
            self.assertIn("25.0", result.output)


if __name__ == "__main__":
    unittest.main()
