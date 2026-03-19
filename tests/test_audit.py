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
from skillsmith.commands.add import add_command
from skillsmith.commands.providers import SkillCandidate


class AuditCommandTests(unittest.TestCase):
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

    def _prepare_project_with_audit_issues(self, cwd: Path) -> None:
        init_result = self.runner.invoke(main, ["init", "--minimal"])
        self.assertEqual(init_result.exit_code, 0, init_result.output)

        add_result = self.runner.invoke(add_command, ["atomic_execution"])
        self.assertEqual(add_result.exit_code, 0, add_result.output)

        (cwd / "AGENTS.md").write_text("drifted", encoding="utf-8")
        skill_file = cwd / ".agent" / "skills" / "atomic_execution" / "SKILL.md"
        skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nTampered\n", encoding="utf-8")
        (cwd / ".agent" / "evals").mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "evals" / "policy.json").write_text(
            json.dumps(
                {
                    "selected_budget_profile": "release",
                    "budget_profiles": {
                        "release": {
                            "pack": "ci",
                            "thresholds": {
                                "min_tacr_delta": 7,
                                "max_latency_increase_ms": 42,
                                "max_cost_increase_usd": 0.03,
                            },
                        }
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        (cwd / ".agent" / "context").mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "context" / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": "2026-03-19T12:00:00Z",
                    "freshness_stamp": "2026-03-19T12:00:00Z",
                    "root": ".",
                    "file_count": 3,
                    "files": [
                        {"path": "AGENTS.md", "freshness_score": 100},
                        {"path": ".agent/project_profile.yaml", "freshness_score": 70},
                        {"path": "README.md", "freshness_score": 25},
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        (cwd / ".agent" / "registry").mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "registry" / "skills.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "generated_at": "2026-03-19T12:00:00Z",
                    "skills": [
                        {
                            "name": "pending-skill",
                            "lifecycle_state": "draft",
                            "approval_status": "pending",
                            "owners": ["alice"],
                            "change_history": [
                                {
                                    "action": "create",
                                    "actor": "alice",
                                    "at": "2026-03-18T09:00:00Z",
                                    "from_state": None,
                                    "to_state": "draft",
                                    "approval_status": "pending",
                                }
                            ],
                        },
                        {
                            "name": "deprecated-skill",
                            "lifecycle_state": "deprecated",
                            "approval_status": "withdrawn",
                            "owners": ["bob"],
                            "change_history": [
                                {
                                    "action": "set-state",
                                    "actor": "bob",
                                    "at": "2026-03-19T08:30:00Z",
                                    "from_state": "draft",
                                    "to_state": "deprecated",
                                    "approval_status": "withdrawn",
                                }
                            ],
                        },
                        {
                            "name": "approved-skill",
                            "lifecycle_state": "approved",
                            "approval_status": "approved",
                            "owners": ["carol"],
                            "change_history": [
                                {
                                    "action": "approve",
                                    "actor": "lead",
                                    "at": "2026-03-19T10:00:00Z",
                                    "from_state": "draft",
                                    "to_state": "approved",
                                    "approval_status": "approved",
                                }
                            ],
                        },
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

    def _audit_mocks(self):
        candidate = SkillCandidate(
            name="atomic_execution",
            description="Atomic execution workflow",
            source="local",
            install_ref="atomic_execution",
            trust_score=95,
            metadata={"starter_pack": True, "starter_pack_label": "library:python"},
        )
        explanation = {
            "reasons": ["starter pack:library:python", "profile:python", "query:python"],
            "matched_query": ["python"],
            "matched_profile": ["python"],
        }
        return [
            mock.patch("skillsmith.commands.audit.shutil.which", return_value="skillsmith"),
            mock.patch("skillsmith.commands.audit.curated_pack_candidates", return_value=[candidate]),
            mock.patch("skillsmith.commands.audit.curated_pack_label", return_value="library:python"),
            mock.patch("skillsmith.commands.audit.explain_candidate", return_value=explanation),
        ]

    def test_audit_reports_combined_health_and_summary(self):
        with self.project_dir() as cwd:
            self._prepare_project_with_audit_issues(cwd)
            patches = self._audit_mocks()
            with mock.patch.dict(os.environ, {"CI": "true"}, clear=False), patches[0], patches[1], patches[2], patches[3]:
                result = self.runner.invoke(main, ["audit"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Skillsmith Audit", result.output)
        self.assertIn("Profile source: saved", result.output)
        self.assertIn("Starter Pack (library:python)", result.output)
        self.assertIn("Eval Policy", result.output)
        self.assertIn("release", result.output)
        self.assertIn("Context Index Freshness", result.output)
        self.assertIn("Registry Governance", result.output)
        self.assertIn("approval pending", result.output.lower())
        self.assertIn("Trust Health", result.output)
        self.assertIn("AGENTS.md is out of sync", result.output)
        self.assertIn("checksum mismatch", result.output)
        self.assertIn("Issues found.", result.output)

    def test_audit_json_emits_machine_readable_payload(self):
        with self.project_dir() as cwd:
            self._prepare_project_with_audit_issues(cwd)
            patches = self._audit_mocks()
            with mock.patch.dict(os.environ, {"CI": "true"}, clear=False), patches[0], patches[1], patches[2], patches[3]:
                result = self.runner.invoke(main, ["audit", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["profile_source"], "saved")
        self.assertEqual(payload["profile_summary"]["starter_pack_label"], "library:python")
        self.assertEqual(payload["eval_policy"]["selected_budget_profile"], "release")
        self.assertEqual(payload["eval_policy"]["ci_enforcement_state"], "enabled")
        self.assertEqual(payload["eval_policy"]["effective_thresholds"]["min_tacr_delta"], 7)
        self.assertEqual(payload["context_index_freshness"]["file_count"], 3)
        self.assertEqual(payload["context_index_freshness"]["stale_count"], 1)
        self.assertEqual(payload["registry_governance"]["approval_pending_count"], 1)
        self.assertEqual(payload["registry_governance"]["deprecated_count"], 1)
        self.assertEqual(payload["registry_governance"]["recent_history_events"][0]["name"], "approved-skill")
        self.assertGreaterEqual(payload["summary"]["warnings"], 1)
        self.assertGreaterEqual(payload["summary"]["errors"], 1)
        self.assertTrue(any(check["path"] == "AGENTS.md" and check["severity"] == "warning" for check in payload["checks"]))
        self.assertTrue(any("checksum mismatch" in check["message"] for check in payload["checks"]))

    def test_audit_strict_exits_non_zero_when_issues_exist(self):
        with self.project_dir() as cwd:
            self._prepare_project_with_audit_issues(cwd)
            patches = self._audit_mocks()
            with patches[0], patches[1], patches[2], patches[3]:
                result = self.runner.invoke(main, ["audit", "--strict"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Issues found.", result.output)

    def test_audit_json_flags_lockfile_signature_mismatch_when_key_is_set(self):
        with self.project_dir() as cwd, mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "audit-secret"}, clear=False
        ):
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            add_result = self.runner.invoke(add_command, ["atomic_execution"])
            self.assertEqual(add_result.exit_code, 0, add_result.output)

            lockfile_path = cwd / "skills.lock.json"
            payload = json.loads(lockfile_path.read_text(encoding="utf-8"))
            payload["skills"][0]["name"] = "tampered"
            lockfile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = self.runner.invoke(main, ["audit", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        audit_payload = json.loads(result.output)
        self.assertTrue(
            any(
                check["section"] == "lockfile"
                and check["severity"] == "error"
                and "signature mismatch" in check["message"]
                for check in audit_payload["checks"]
            )
        )

    def test_audit_surfaces_trust_health(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace(
                "trusted_publisher_keys: {}", "trusted_publisher_keys:\n  publisher-demo: publisher-secret"
            )
            profile_path.write_text(profile_text, encoding="utf-8")

            trust_dir = cwd / ".agent" / "trust"
            trust_dir.mkdir(parents=True, exist_ok=True)
            (trust_dir / "publisher_revocations.json").write_text(
                json.dumps({"revoked_key_ids": ["publisher-demo"]}, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            (trust_dir / "transparency_log.jsonl").write_text(
                json.dumps(
                    {
                        "logged_at": "2026-03-19T12:00:00Z",
                        "state": "valid",
                        "valid": True,
                        "key_id": "publisher-demo",
                        "artifact_path": ".agent/skills/remote_signed",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.runner.invoke(main, ["audit", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["trust_health"]["revocations"]["revoked_key_ids"], ["publisher-demo"])
        self.assertEqual(payload["trust_health"]["revocations"]["revoked_trusted_key_ids"], ["publisher-demo"])
        self.assertEqual(payload["trust_health"]["transparency_log"]["entry_count"], 1)
        self.assertTrue(any(check["section"] == "trust" for check in payload["checks"]))
        self.assertTrue(
            any(
                check["section"] == "trust" and check["severity"] == "warning" and "publisher_revocations.json" in check["message"]
                for check in payload["checks"]
            )
        )


if __name__ == "__main__":
    unittest.main()
