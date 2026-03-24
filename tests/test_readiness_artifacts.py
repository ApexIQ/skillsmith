from __future__ import annotations

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
from skillsmith import readiness_artifacts


def _sample_report() -> dict:
    return {
        "profile_source": "saved",
        "profile": {
            "idea": "Project using skillsmith",
            "project_stage": "existing",
            "app_type": "library",
            "languages": ["python"],
            "frameworks": ["click", "pytest"],
            "package_manager": "uv",
            "deployment_target": "github-actions",
            "priorities": ["testability", "verification"],
            "target_tools": ["codex", "claude"],
        },
        "query": "python click pytest",
        "starter_pack_label": "library:python",
        "starter_pack": [
            {
                "name": "python-packaging",
                "source": "local",
                "why": ["starter pack match"],
            }
        ],
        "policy": {"allow_remote_skills": False},
        "trust_health": {"revocations": {"valid": True}, "transparency_log": {"valid": True}},
        "provider_reliability": [],
        "eval_policy": {"gate_enabled": True, "ci_enforced": True, "ci_opt_out": False},
        "context_index_freshness": {"present": False, "valid": False, "file_count": 0, "average_freshness_score": 0.0},
        "registry_governance": {"present": False, "entry_count": 0, "approval_pending_count": 0, "deprecated_count": 0},
        "snapshot_files": {},
        "readiness_summary": {
            "ready": True,
            "status": "ready",
            "score": 92,
            "summary": "ready (92/100)",
            "blockers": [],
            "warnings": ["context index has 1 stale file"],
        },
    }


class ReadinessArtifactTests(unittest.TestCase):
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

    def test_write_readiness_artifacts_writes_expected_files(self):
        with self.project_dir() as cwd:
            artifact_dir = cwd / "artifacts"

            outputs = readiness_artifacts.write_readiness_artifacts(
                artifact_dir,
                _sample_report(),
                generated_at="2026-03-24T10:15:00Z",
            )

            self.assertEqual(sorted(outputs.keys()), ["readiness_pr.md", "report.json", "scorecard.json"])
            self.assertTrue(outputs["report.json"].exists())
            self.assertTrue(outputs["readiness_pr.md"].exists())
            self.assertTrue(outputs["scorecard.json"].exists())

            report_payload = json.loads(outputs["report.json"].read_text(encoding="utf-8"))
            self.assertEqual(report_payload, _sample_report())

            pr_text = outputs["readiness_pr.md"].read_text(encoding="utf-8")
            self.assertIn("## Skillsmith Readiness", pr_text)
            self.assertIn("- Ready: yes", pr_text)
            self.assertIn("- Score: 92/100", pr_text)
            self.assertIn("- Starter pack: library:python", pr_text)

            scorecard_payload = json.loads(outputs["scorecard.json"].read_text(encoding="utf-8"))
            self.assertEqual(scorecard_payload["generated_at"], "2026-03-24T10:15:00Z")
            self.assertEqual(scorecard_payload["schema_version"], 1)
            self.assertEqual(scorecard_payload["readiness"]["score"], 92)
            self.assertEqual(scorecard_payload["metrics"]["activation"]["first_run_success_rate_pct"], None)
            self.assertEqual(scorecard_payload["metrics"]["retention"]["day_30_team_retention_pct"], None)
            self.assertIn("activation", scorecard_payload["metric_schema"])
            self.assertIn("retention", scorecard_payload["metric_schema"])
            self.assertIn("time_to_first_readiness_minutes", scorecard_payload["metric_schema"]["activation"])
            self.assertIn("weekly_active_repo_count", scorecard_payload["metric_schema"]["retention"])

    def test_report_artifact_dir_preserves_stdout_and_matches_json_output(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            artifact_dir = cwd / "readiness-artifacts"

            artifact_run = self.runner.invoke(main, ["report", "--artifact-dir", str(artifact_dir)])
            self.assertEqual(artifact_run.exit_code, 0, artifact_run.output)

            plain_run = self.runner.invoke(main, ["report"])
            self.assertEqual(plain_run.exit_code, 0, plain_run.output)
            self.assertEqual(artifact_run.output, plain_run.output)

            json_run = self.runner.invoke(main, ["report", "--json"])
            self.assertEqual(json_run.exit_code, 0, json_run.output)

            report_path = artifact_dir / "report.json"
            pr_path = artifact_dir / "readiness_pr.md"
            scorecard_path = artifact_dir / "scorecard.json"
            self.assertTrue(report_path.exists())
            self.assertTrue(pr_path.exists())
            self.assertTrue(scorecard_path.exists())

            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8")), json.loads(json_run.output))
            self.assertIn("## Skillsmith Readiness", pr_path.read_text(encoding="utf-8"))
            self.assertIn("generated_at", json.loads(scorecard_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
