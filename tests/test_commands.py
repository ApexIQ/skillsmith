import json
import hashlib
import hmac
import os
import re
import shutil
import tempfile
import time
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
import uuid
from unittest import mock

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main
from skillsmith.commands import TEMPLATE_DIR, find_template_skill_dir
from skillsmith.commands.add import add_command
from skillsmith.commands.align import align_command
from skillsmith.commands.budget import budget_command
from skillsmith.commands.compose import compose_command
from skillsmith.commands.discover import discover_command
from skillsmith.commands.doctor import doctor_command
from skillsmith.commands.lint import lint_command
from skillsmith.commands.list_cmd import list_command
from skillsmith.commands.rebuild import rebuild_command
from skillsmith.commands.report import report_command
from skillsmith.commands.serve import serve_command
from skillsmith.commands.snapshot import snapshot_command
from skillsmith.commands.init import _infer_project_profile, _merge_profile
from skillsmith.commands.update import update_command
from skillsmith.commands.watch import watch_command
from skillsmith.commands.lockfile import verify_remote_skill_artifact
from skillsmith.commands.providers import (
    GitHubTopicsProvider,
    HuggingFaceProvider,
    SkillCandidate,
    OrgRegistryProvider,
    SkillsShProvider,
    PROVIDER_SOURCE_ORDER,
    curated_pack_candidates,
    explain_candidate,
    rank_candidates,
    recommend_skills_for_profile,
)
from skillsmith.commands.workflow_engine import build_workflow, load_rolling_eval_feedback


def make_skill(skill_dir: Path, version: str = "0.1.0", description: str = "Test skill description") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        f"version: {version}\n"
        f"name: {skill_dir.name}\n"
        f"description: {description}\n"
        "tags: [testing]\n"
        "---\n"
        "# Instructions\n"
        "This skill body is long enough to satisfy validation requirements.\n",
        encoding="utf-8",
    )


def downgrade_skill_version(content: str) -> str:
    return re.sub(r"version:\s*[^\n]+", "version: 0.0.1", content, count=1)


def write_signed_remote_skill(target: Path, *, key_id: str = "publisher-demo", key: str = "publisher-secret", valid: bool = True) -> None:
    target.mkdir(parents=True, exist_ok=True)
    skill_text = "---\nname: remote-skill\ndescription: test\nversion: 1.0.0\n---\nbody"
    skill_path = target / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")

    manifest = {
        "algorithm": "sha256",
        "files": [
            {
                "path": "SKILL.md",
                "sha256": hashlib.sha256(skill_path.read_bytes()).hexdigest(),
            }
        ],
    }
    manifest_text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    (target / "skillsmith.manifest.json").write_text(manifest_text, encoding="utf-8")
    signature = hmac.new(key.encode("utf-8"), manifest_text.encode("utf-8"), hashlib.sha256).hexdigest()
    if not valid:
        signature = "0" * len(signature)
    (target / "skillsmith.sig").write_text(
        json.dumps({"algorithm": "hmac-sha256", "key_id": key_id, "signature": signature}, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def write_latest_eval_artifact(
    target: Path,
    *,
    tacr: float,
    total_interventions: int,
    delta_tacr: float = 0.0,
    policy: dict | None = None,
) -> None:
    artifact_path = target / ".agent" / "evals" / "results" / "latest.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-03-19T00:00:00Z",
                "source": ".agent/evals/runs.json",
                "summary": {
                    "total_runs": 4,
                    "successful_runs": 2,
                    "tacr": tacr,
                    "avg_latency_ms": 1200,
                    "avg_cost_usd": 0.2,
                    "total_interventions": total_interventions,
                },
                "trend": {
                    "available": True,
                    "baseline_artifact": "eval-previous.json",
                    "delta_tacr": delta_tacr,
                    "delta_avg_latency_ms": 75,
                    "delta_avg_cost_usd": 0.05,
                },
                "runs": [],
                "policy": policy or {},
            }
        ),
        encoding="utf-8",
    )


def write_eval_history_artifact(
    target: Path,
    *,
    artifact_name: str,
    generated_at: str,
    tacr: float,
    total_interventions: int,
    avg_latency_ms: int,
    avg_cost_usd: float,
    policy: dict | None = None,
) -> None:
    artifact_path = target / ".agent" / "evals" / "results" / artifact_name
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": generated_at,
                "source": ".agent/evals/runs.json",
                "summary": {
                    "total_runs": 4,
                    "successful_runs": 2,
                    "tacr": tacr,
                    "avg_latency_ms": avg_latency_ms,
                    "avg_cost_usd": avg_cost_usd,
                    "total_interventions": total_interventions,
                },
                "trend": {"available": False},
                "runs": [],
                "policy": policy or {},
            }
        ),
        encoding="utf-8",
    )
    os.utime(artifact_path, None)


def write_context_index_fixture(target: Path) -> None:
    index_path = target / ".agent" / "context" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-03-19T12:00:00Z",
                "freshness_stamp": "2026-03-19T12:00:00Z",
                "root": ".",
                "file_count": 3,
                "files": [
                    {
                        "path": "AGENTS.md",
                        "exists": True,
                        "size_bytes": 120,
                        "freshness_stamp": "2026-03-19T12:00:00Z",
                        "age_seconds": 0,
                        "freshness_score": 100,
                        "path_priority_rank": 1,
                        "path_priority_score": 100,
                        "compressed_snippet": "Read the profile first.",
                    },
                    {
                        "path": ".agent/project_profile.yaml",
                        "exists": True,
                        "size_bytes": 240,
                        "freshness_stamp": "2026-03-18T12:00:00Z",
                        "age_seconds": 86400,
                        "freshness_score": 70,
                        "path_priority_rank": 2,
                        "path_priority_score": 92,
                        "compressed_snippet": "Profile is current.",
                    },
                    {
                        "path": "README.md",
                        "exists": True,
                        "size_bytes": 300,
                        "freshness_stamp": "2026-03-13T12:00:00Z",
                        "age_seconds": 518400,
                        "freshness_score": 25,
                        "path_priority_rank": 3,
                        "path_priority_score": 84,
                        "compressed_snippet": "Older overview.",
                    },
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def write_registry_fixture(target: Path) -> None:
    registry_path = target / ".agent" / "registry" / "skills.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
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
                            },
                            {
                                "action": "request-approval",
                                "actor": "alice",
                                "at": "2026-03-19T09:00:00Z",
                                "from_state": "draft",
                                "to_state": "draft",
                                "approval_status": "pending",
                            },
                        ],
                        "approvals": [],
                    },
                    {
                        "name": "deprecated-skill",
                        "lifecycle_state": "deprecated",
                        "approval_status": "withdrawn",
                        "owners": ["bob"],
                        "change_history": [
                            {
                                "action": "create",
                                "actor": "bob",
                                "at": "2026-03-17T09:00:00Z",
                                "from_state": None,
                                "to_state": "draft",
                                "approval_status": "not_requested",
                            },
                            {
                                "action": "set-state",
                                "actor": "bob",
                                "at": "2026-03-19T08:30:00Z",
                                "from_state": "draft",
                                "to_state": "deprecated",
                                "approval_status": "withdrawn",
                            },
                        ],
                        "approvals": [],
                    },
                    {
                        "name": "approved-skill",
                        "lifecycle_state": "approved",
                        "approval_status": "approved",
                        "owners": ["carol"],
                        "change_history": [
                            {
                                "action": "create",
                                "actor": "carol",
                                "at": "2026-03-16T09:00:00Z",
                                "from_state": None,
                                "to_state": "draft",
                                "approval_status": "not_requested",
                            },
                            {
                                "action": "approve",
                                "actor": "lead",
                                "at": "2026-03-19T10:00:00Z",
                                "from_state": "draft",
                                "to_state": "approved",
                                "approval_status": "approved",
                            },
                        ],
                        "approvals": [
                            {
                                "decision": "approved",
                                "actor": "lead",
                                "at": "2026-03-19T10:00:00Z",
                                "from_state": "draft",
                                "to_state": "approved",
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


def write_eval_policy_fixture(target: Path) -> None:
    policy_path = target / ".agent" / "evals" / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
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


def snapshot_json_files(target: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    agent_dir = target / ".agent"
    if not agent_dir.exists():
        return snapshot
    for path in sorted(agent_dir.rglob("*.json")):
        snapshot[path.relative_to(target).as_posix()] = path.read_text(encoding="utf-8")
    return snapshot


class SkillsmithCommandTests(unittest.TestCase):
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

    def test_init_creates_agent_workspace(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(main, ["init", "--minimal"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((cwd / "AGENTS.md").exists())
            self.assertTrue((cwd / "CLAUDE.md").exists())
            self.assertTrue((cwd / ".agent" / "PROJECT.md").exists())
            self.assertTrue((cwd / ".agent" / "STATE.md").exists())
            self.assertTrue((cwd / ".agent" / "project_profile.yaml").exists())
            self.assertTrue((cwd / ".agent" / "context" / "project-context.md").exists())
            self.assertTrue((cwd / ".agent" / "rules" / "README.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "discover-project.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "brainstorm.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "plan-feature.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "implement-feature.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "debug-issue.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "review-changes.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "test-changes.md").exists())
            self.assertTrue((cwd / ".agent" / "workflows" / "deploy-checklist.md").exists())
            self.assertTrue((cwd / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((cwd / ".claude" / "agents" / "orchestrator.md").exists())
            self.assertTrue((cwd / ".claude" / "agents" / "researcher.md").exists())
            self.assertTrue((cwd / ".claude" / "agents" / "implementer.md").exists())
            self.assertTrue((cwd / ".claude" / "agents" / "reviewer.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "brainstorm.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "plan-feature.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "implement-feature.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "review-changes.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "test-changes.md").exists())
            self.assertTrue((cwd / ".claude" / "commands" / "deploy-checklist.md").exists())
            self.assertTrue((cwd / ".cursor" / "rules" / "workflows" / "brainstorm.mdc").exists())
            self.assertTrue((cwd / ".windsurf" / "rules" / "skillsmith.md").exists())
            self.assertTrue((cwd / ".windsurf" / "workflows" / "brainstorm.md").exists())
            self.assertTrue((cwd / ".zencoder" / "rules" / "skillsmith.md").exists())
            self.assertTrue((cwd / ".zencoder" / "rules" / "workflows" / "deploy-checklist.md").exists())

            profile_text = (cwd / ".agent" / "project_profile.yaml").read_text(encoding="utf-8")
            context_text = (cwd / ".agent" / "context" / "project-context.md").read_text(encoding="utf-8")
            agents_text = (cwd / "AGENTS.md").read_text(encoding="utf-8")
            project_text = (cwd / ".agent" / "PROJECT.md").read_text(encoding="utf-8")
            workflow_text = (cwd / ".agent" / "workflows" / "plan-feature.md").read_text(encoding="utf-8")
            command_text = (cwd / ".claude" / "commands" / "plan-feature.md").read_text(encoding="utf-8")
            cursor_workflow_text = (cwd / ".cursor" / "rules" / "workflows" / "brainstorm.mdc").read_text(encoding="utf-8")
            windsurf_workflow_text = (cwd / ".windsurf" / "workflows" / "brainstorm.md").read_text(encoding="utf-8")
            zencoder_workflow_text = (cwd / ".zencoder" / "rules" / "workflows" / "deploy-checklist.md").read_text(encoding="utf-8")
            self.assertIn("project_stage: greenfield", profile_text)
            self.assertIn("# Project Context", context_text)
            self.assertIn("Project using skillsmith", agents_text)
            self.assertIn("Project using skillsmith", project_text)
            self.assertIn("# Workflow: plan-feature", workflow_text)
            self.assertIn(".agent/workflows/plan-feature.md", command_text)
            self.assertIn("Allow remote skills: false", context_text)
            self.assertIn("Blocked sources: none", context_text)
            self.assertIn("Require pinned GitHub refs: true", context_text)
            self.assertIn("Trusted publisher keys: none", context_text)
            self.assertIn("Trusted publisher public keys: none", context_text)
            self.assertIn("Publisher verification mode: optional", context_text)
            self.assertIn("Publisher signature scheme mode: auto", context_text)
            self.assertIn("Allowed publisher signature algorithms: hmac-sha256, rsa-sha256", context_text)
            self.assertIn("Publisher key rotation: none", context_text)
            self.assertIn("Minimum remote freshness: 0", context_text)
            self.assertIn("Required remote licenses: none", context_text)
            self.assertIn("blocked_skill_sources: []", profile_text)
            self.assertIn("require_pinned_github_refs: true", profile_text)
            self.assertIn("trusted_publisher_keys: {}", profile_text)
            self.assertIn("trusted_publisher_public_keys: {}", profile_text)
            self.assertIn("publisher_verification_mode: optional", profile_text)
            self.assertIn("publisher_signature_scheme_mode: auto", profile_text)
            self.assertIn("publisher_signature_algorithms:", profile_text)
            self.assertIn("- hmac-sha256", profile_text)
            self.assertIn("- rsa-sha256", profile_text)
            self.assertIn("publisher_key_rotation: {}", profile_text)
            self.assertIn("min_remote_freshness_score: 0", profile_text)
            self.assertIn("required_remote_licenses: []", profile_text)
            self.assertIn(".agent/workflows/brainstorm.md", cursor_workflow_text)
            self.assertIn("# Workflow: brainstorm", windsurf_workflow_text)
            self.assertIn(".agent/workflows/deploy-checklist.md", zencoder_workflow_text)
            self.assertIn("brainstorm", (cwd / ".windsurf" / "rules" / "skillsmith.md").read_text(encoding="utf-8"))
            self.assertIn(".agent/workflows/", (cwd / ".zencoder" / "rules" / "skillsmith.md").read_text(encoding="utf-8"))

    def test_infer_profile_detects_python_library_shape(self):
        with self.project_dir() as cwd:
            (cwd / "pyproject.toml").write_text(
                "[project]\nname='skillsmith'\n"
                "dependencies=['click','pytest']\n",
                encoding="utf-8",
            )
            (cwd / "src").mkdir()
            (cwd / "tests").mkdir()

            profile = _infer_project_profile(cwd)

            self.assertEqual(profile["app_type"], "library")
            self.assertEqual(profile["deployment_target"], "not-specified")
            self.assertIn("python", profile["languages"])
            self.assertIn("pytest", profile["frameworks"])
            self.assertIn("testability", profile["priorities"])
            self.assertIn("python -m unittest", profile["test_commands"])

    def test_infer_profile_detects_fullstack_signals(self):
        with self.project_dir() as cwd:
            (cwd / "pyproject.toml").write_text(
                "[project]\nname='api'\ndependencies=['fastapi']\n",
                encoding="utf-8",
            )
            (cwd / "package.json").write_text(
                json.dumps(
                    {
                        "name": "web-app",
                        "dependencies": {"next": "14.0.0", "react": "18.0.0"},
                        "scripts": {"build": "next build", "test": "vitest"},
                    }
                ),
                encoding="utf-8",
            )
            (cwd / "vercel.json").write_text("{}", encoding="utf-8")
            (cwd / ".cursor").mkdir(exist_ok=True)
            (cwd / ".windsurf").mkdir()
            (cwd / ".github" / "workflows").mkdir(parents=True)
            (cwd / ".github" / "workflows" / "ci.yml").write_text("name: ci", encoding="utf-8")

            profile = _infer_project_profile(cwd)

            self.assertEqual(profile["app_type"], "fullstack-app")
            self.assertEqual(profile["deployment_target"], "vercel")
            self.assertIn("fastapi", profile["frameworks"])
            self.assertIn("next", profile["frameworks"])
            self.assertIn("cursor", profile["target_tools"])
            self.assertIn("windsurf", profile["target_tools"])
            self.assertIn("automation", profile["priorities"])
            self.assertIn("speed", profile["priorities"])
            self.assertIn("npm run build", profile["build_commands"])

    def test_init_guided_writes_answers_to_profile(self):
        with self.project_dir() as cwd:
            user_input = "\n".join(
                [
                    "AI release automation platform",
                    "greenfield",
                    "saas",
                    "python, typescript",
                    "fastapi, next",
                    "uv",
                    "fly.io",
                    "speed, maintainability",
                    "codex, claude, cursor",
                    "y",
                    "local, github, skills.sh",
                    "github, gitlab",
                    "y",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "65",
                    "8",
                    "",
                    "MIT, Apache-2.0",
                ]
            )

            result = self.runner.invoke(main, ["init", "--minimal", "--guided"], input=user_input + "\n")

            self.assertEqual(result.exit_code, 0, result.output)
            profile_text = (cwd / ".agent" / "project_profile.yaml").read_text(encoding="utf-8")
            context_text = (cwd / ".agent" / "context" / "project-context.md").read_text(encoding="utf-8")
            self.assertIn("idea: AI release automation platform", profile_text)
            self.assertIn("project_stage: greenfield", profile_text)
            self.assertIn("min_remote_trust_score: 65", profile_text)
            self.assertIn("min_remote_freshness_score: 8", profile_text)
            self.assertIn("blocked_skill_sources:", profile_text)
            self.assertIn("require_pinned_github_refs: true", profile_text)
            self.assertIn("trusted_publisher_public_keys: {}", profile_text)
            self.assertIn("publisher_signature_scheme_mode: auto", profile_text)
            self.assertIn("publisher_signature_algorithms:", profile_text)
            self.assertIn("- github", profile_text)
            self.assertIn("publisher_key_rotation: {}", profile_text)
            self.assertIn("required_remote_licenses:", profile_text)
            self.assertIn("- MIT", profile_text)
            self.assertIn("- python", context_text)
            self.assertIn("- codex", context_text)
            self.assertIn("Blocked sources: github, gitlab", context_text)
            self.assertIn("Require pinned GitHub refs: true", context_text)
            self.assertIn("Trusted publisher public keys: none", context_text)
            self.assertIn("Publisher signature scheme mode: auto", context_text)
            self.assertIn("Allowed publisher signature algorithms: hmac-sha256, rsa-sha256", context_text)
            self.assertIn("Publisher key rotation: none", context_text)
            self.assertIn("Minimum remote freshness: 8", context_text)
            self.assertIn("Required remote licenses: MIT, Apache-2.0", context_text)

    def test_init_guided_auto_installs_recommended_skills(self):
        candidate = SkillCandidate(
            name="atomic_execution",
            description="Atomic execution workflow",
            source="local",
            install_ref="atomic_execution",
            trust_score=90,
            metadata={"recommendation": {"reasons": ["starter pack:library:pytest", "profile:python"]}},
        )
        explanation = {
            "reasons": ["starter pack:library:pytest", "profile:python"],
            "matched_query": ["python"],
            "matched_profile": ["pytest"],
        }
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.init.explain_recommendations_for_profile", return_value=[(candidate, explanation)]
        ):
            user_input = "\n".join(
                [
                    "AI release automation platform",
                    "greenfield",
                    "saas",
                    "python, typescript",
                    "fastapi, next",
                    "uv",
                    "fly.io",
                    "speed, maintainability",
                    "codex, claude, cursor",
                    "n",
                    "",
                    "y",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "65",
                    "0",
                    "",
                    "",
                ]
            )

            result = self.runner.invoke(main, ["init", "--minimal", "--guided"], input=user_input + "\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((cwd / ".agent" / "skills" / "atomic_execution" / "SKILL.md").exists())
            self.assertIn("Installed recommended skills", result.output)
            self.assertIn("starter pack", result.output)
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lockfile["skills"][0]["name"], "atomic_execution")
            self.assertIn("recommendation", lockfile["skills"][0])

    def test_merge_profile_backfills_new_policy_defaults(self):
        with self.project_dir() as cwd:
            inferred = _infer_project_profile(cwd)
            legacy_profile = {
                "idea": "Legacy project",
                "allow_remote_skills": True,
                "trusted_skill_sources": ["local", "github"],
                "min_remote_trust_score": 72,
                "build_commands": ["legacy build"],
                "test_commands": ["legacy test"],
            }

            merged = _merge_profile(legacy_profile, inferred)

            self.assertEqual(merged["idea"], "Legacy project")
            self.assertEqual(merged["trusted_skill_sources"], ["local", "github"])
            self.assertEqual(merged["min_remote_trust_score"], 72)
            self.assertEqual(merged["blocked_skill_sources"], [])
            self.assertTrue(merged["require_pinned_github_refs"])
            self.assertEqual(merged["trusted_publisher_keys"], {})
            self.assertEqual(merged["trusted_publisher_public_keys"], {})
            self.assertEqual(merged["publisher_signature_scheme_mode"], "auto")
            self.assertEqual(merged["publisher_signature_algorithms"], ["hmac-sha256", "rsa-sha256"])
            self.assertEqual(merged["publisher_key_rotation"], {})
            self.assertEqual(merged["min_remote_freshness_score"], 0)
            self.assertEqual(merged["required_remote_licenses"], [])
            self.assertEqual(merged["build_commands"], inferred["build_commands"])
            self.assertEqual(merged["test_commands"], inferred["test_commands"])

    def test_align_rerenders_from_saved_profile(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("idea: Project using skillsmith", "idea: Aligned platform")
            profile_text = profile_text.replace("package_manager: unknown", "package_manager: uv")
            profile_path.write_text(profile_text, encoding="utf-8")

            result = self.runner.invoke(align_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Re-rendered managed files", result.output)
            self.assertIn("Aligned platform", (cwd / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("Package manager: uv", (cwd / ".agent" / "PROJECT.md").read_text(encoding="utf-8"))
            self.assertIn("Aligned platform", (cwd / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("Aligned platform", (cwd / ".agent" / "workflows" / "plan-feature.md").read_text(encoding="utf-8"))

    def test_align_prunes_unselected_tool_outputs(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("- windsurf\n", "")
            profile_text = profile_text.replace("- zencoder\n", "")
            profile_text = profile_text.replace("- gemini\n", "")
            profile_path.write_text(profile_text, encoding="utf-8")

            result = self.runner.invoke(align_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertFalse((cwd / ".windsurf" / "rules" / "skillsmith.md").exists())
            self.assertFalse((cwd / ".windsurf" / "workflows" / "brainstorm.md").exists())
            self.assertFalse((cwd / ".zencoder" / "rules" / "skillsmith.md").exists())
            self.assertFalse((cwd / ".zencoder" / "rules" / "workflows" / "deploy-checklist.md").exists())
            self.assertFalse((cwd / "GEMINI.md").exists())
            self.assertTrue((cwd / "CLAUDE.md").exists())

    def test_align_prunes_cursor_workflow_outputs_when_cursor_removed(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("- cursor\n", "")
            profile_path.write_text(profile_text, encoding="utf-8")

            result = self.runner.invoke(align_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertFalse((cwd / ".cursor" / "rules" / "skillsmith.mdc").exists())
            self.assertFalse((cwd / ".cursor" / "rules" / "workflows" / "brainstorm.mdc").exists())

    def test_add_copies_local_template_skill(self):
        with self.project_dir() as cwd:
            result = self.runner.invoke(add_command, ["atomic_execution"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((cwd / ".agent" / "skills" / "atomic_execution" / "SKILL.md").exists())
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["name"], "atomic_execution")
            self.assertEqual(entry["source"], "local")
            self.assertEqual(entry["provenance"]["install_kind"], "local-template")
            self.assertEqual(entry["provenance"]["selected_by"], "manual")
            self.assertEqual(entry["recommendation"]["selection_mode"], "manual")
            self.assertIn("manual install", entry["recommendation"]["reasons"])
            self.assertIn("local template", entry["recommendation"]["reasons"])

    def test_add_suggests_discovered_skills_when_missing(self):
        candidates = [
            SkillCandidate(
                name="python-packaging",
                description="Packaging workflows",
                source="skills.sh",
                install_ref="wshobson/agents/python-packaging",
            )
        ]
        with self.project_dir(), mock.patch("skillsmith.commands.add.discover_skills", return_value=candidates):
            result = self.runner.invoke(add_command, ["missing-skill"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("not found locally", result.output)
        self.assertIn("python-packaging", result.output)

    def test_add_discover_installs_remote_skill_and_writes_lockfile(self):
        candidate = SkillCandidate(
            name="python-packaging",
            description="Packaging workflows",
            source="skills.sh",
            version="1.2.0",
            install_ref="wshobson/agents/python-packaging",
            trust_score=70,
            metadata={"install_url": "https://github.com/wshobson/agents/tree/0123456789abcdef0123456789abcdef01234567/python-packaging"},
        )
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.add.discover_skills", return_value=[candidate]
        ), mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("allow_remote_skills: false", "allow_remote_skills: true")
            profile_text = profile_text.replace("- local", "- local\n- skills.sh")
            profile_path.write_text(profile_text, encoding="utf-8")

            def fake_download(url, target):
                target.mkdir(parents=True, exist_ok=True)
                (target / "SKILL.md").write_text("---\nname: python-packaging\ndescription: test\nversion: 1.2.0\n---\nbody", encoding="utf-8")

            download.side_effect = fake_download
            result = self.runner.invoke(add_command, ["python packaging", "--discover"])

            self.assertEqual(result.exit_code, 0, result.output)
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["source"], "skills.sh")
            self.assertEqual(entry["install_ref"], "wshobson/agents/python-packaging")
            self.assertEqual(entry["provenance"]["install_kind"], "remote-url")
            self.assertEqual(entry["provenance"]["selected_by"], "skillsmith-discovery")
            self.assertEqual(entry["recommendation"]["selection_mode"], "discovery")
            joined_reasons = " | ".join(entry["recommendation"]["reasons"])
            self.assertIn("query:", joined_reasons)
            self.assertIn("python", joined_reasons)
            self.assertIn("source:+", joined_reasons)
            self.assertTrue((cwd / ".agent" / "skills" / "python-packaging" / "SKILL.md").exists())

    def test_add_direct_url_installs_and_writes_manual_audit_metadata(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("publisher_verification_mode: optional", "publisher_verification_mode: required")
            profile_text = profile_text.replace("trusted_publisher_keys: {}", "trusted_publisher_keys:\n  publisher-demo: publisher-secret")
            profile_path.write_text(profile_text, encoding="utf-8")

            def fake_download(url, target):
                write_signed_remote_skill(target)

            download.side_effect = fake_download
            result = self.runner.invoke(add_command, ["https://github.com/example/repo/tree/0123456789abcdef0123456789abcdef01234567/direct-skill"])

            self.assertEqual(result.exit_code, 0, result.output)
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["source"], "github")
            self.assertEqual(entry["provenance"]["install_kind"], "manual-url")
            self.assertEqual(entry["provenance"]["selected_by"], "manual")
            self.assertEqual(entry["metadata"]["publisher_verification"]["state"], "valid")
            self.assertEqual(entry["metadata"]["publisher_verification"]["key_id"], "publisher-demo")
            self.assertEqual(entry["provenance"]["publisher_verification"]["state"], "valid")
            self.assertEqual(entry["recommendation"]["selection_mode"], "manual")
            self.assertIn("manual install", entry["recommendation"]["reasons"])
            self.assertIn("GitHub URL", entry["recommendation"]["reasons"])

    def test_add_rejects_signed_artifact_when_required_mode_and_signature_is_invalid(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("publisher_verification_mode: optional", "publisher_verification_mode: required")
            profile_text = profile_text.replace("trusted_publisher_keys: {}", "trusted_publisher_keys:\n  publisher-demo: publisher-secret")
            profile_path.write_text(profile_text, encoding="utf-8")

            def fake_download(url, target):
                write_signed_remote_skill(target, valid=False)

            download.side_effect = fake_download
            result = self.runner.invoke(add_command, ["https://github.com/example/repo/tree/0123456789abcdef0123456789abcdef01234567/direct-skill"])

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("publisher signature mismatch", result.output)
            self.assertFalse((cwd / ".agent" / "skills" / "direct-skill").exists())
            self.assertFalse((cwd / "skills.lock.json").exists())

    def test_add_rejects_revoked_publisher_key_even_when_signature_is_valid(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
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

            def fake_download(url, target):
                write_signed_remote_skill(target)

            download.side_effect = fake_download
            result = self.runner.invoke(
                add_command,
                ["https://github.com/example/repo/tree/0123456789abcdef0123456789abcdef01234567/direct-skill"],
            )

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("revoked", result.output)
            self.assertFalse((cwd / ".agent" / "skills" / "direct-skill").exists())
            self.assertFalse((cwd / "skills.lock.json").exists())
            log_path = cwd / ".agent" / "trust" / "transparency_log.jsonl"
            self.assertTrue(log_path.exists())
            self.assertIn('"state":"revoked"', log_path.read_text(encoding="utf-8"))

    def test_add_allows_optional_signature_failures_but_records_verification_state(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("trusted_publisher_keys: {}", "trusted_publisher_keys:\n  publisher-demo: publisher-secret")
            profile_path.write_text(profile_text, encoding="utf-8")

            def fake_download(url, target):
                write_signed_remote_skill(target, valid=False)

            download.side_effect = fake_download
            result = self.runner.invoke(add_command, ["https://github.com/example/repo/tree/0123456789abcdef0123456789abcdef01234567/direct-skill"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("publisher signature mismatch", result.output)
            self.assertTrue((cwd / ".agent" / "skills" / "direct-skill" / "SKILL.md").exists())
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            entry = lockfile["skills"][0]
            self.assertEqual(entry["metadata"]["publisher_verification"]["state"], "invalid")
            self.assertEqual(entry["metadata"]["publisher_verification"]["mode"], "optional")

    def test_add_discover_blocks_low_trust_remote_skill(self):
        candidate = SkillCandidate(
            name="low-trust-skill",
            description="Remote skill with low trust",
            source="skills.sh",
            version="0.1.0",
            install_ref="vendor/skills@low-trust-skill",
            trust_score=40,
            metadata={"install_url": "https://github.com/vendor/skills/tree/0123456789abcdef0123456789abcdef01234567/low-trust-skill"},
        )
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.add.discover_skills", return_value=[candidate]
        ), mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("allow_remote_skills: false", "allow_remote_skills: true")
            profile_text = profile_text.replace("- local", "- local\n- skills.sh")
            profile_path.write_text(profile_text, encoding="utf-8")

            result = self.runner.invoke(add_command, ["low trust", "--discover"])

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("blocked", result.output)
            self.assertIn("min_remote_trust_score 65", result.output)
            download.assert_not_called()
            self.assertFalse((cwd / ".agent" / "skills" / "low-trust-skill").exists())

    def test_discover_command_renders_ranked_results(self):
        candidates = [
            SkillCandidate(name="alpha", description="desc", source="local", install_ref="alpha", trust_score=90, metadata={"starter_pack": True, "starter_pack_label": "library:pytest"}),
            SkillCandidate(name="beta", description="desc", source="skills.sh", install_ref="beta/ref", trust_score=70),
        ]
        with self.project_dir(), mock.patch("skillsmith.commands.discover.discover_skills", return_value=candidates):
            result = self.runner.invoke(discover_command, ["python packaging"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("alpha", result.output)
        self.assertIn("beta", result.output)
        self.assertIn("skills.sh", result.output)
        self.assertIn("starter", result.output)
        self.assertIn("pack", result.output)
        self.assertIn("Why", result.output)

    def test_discover_command_lists_all_providers_including_huggingface(self):
        candidates = [
            SkillCandidate(name="alpha", description="desc", source="local", install_ref="alpha", trust_score=90),
            SkillCandidate(name="beta", description="desc", source="skills.sh", install_ref="beta/ref", trust_score=70),
            SkillCandidate(name="gamma", description="desc", source="huggingface", install_ref="gamma", trust_score=68),
            SkillCandidate(name="delta", description="desc", source="github-topics", install_ref="delta", trust_score=72),
            SkillCandidate(name="epsilon", description="desc", source="org-registry", install_ref="epsilon", trust_score=84),
        ]
        with mock.patch("skillsmith.commands.discover.discover_skills", return_value=candidates):
            result = self.runner.invoke(discover_command, ["python packaging"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(f"Searched providers: {', '.join(PROVIDER_SOURCE_ORDER)}", result.output)
        self.assertIn("gamma", result.output)
        self.assertIn("huggingface", result.output)
        self.assertIn("github-topics", result.output)
        self.assertIn("org-registry", result.output)

    def test_discover_command_accepts_huggingface_source(self):
        with mock.patch("skillsmith.commands.discover.discover_skills", return_value=[]):
            result = self.runner.invoke(discover_command, ["python packaging", "--source", "huggingface"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No skills found", result.output)

    def test_discover_command_accepts_github_topics_source(self):
        with mock.patch("skillsmith.commands.discover.discover_skills", return_value=[]):
            result = self.runner.invoke(discover_command, ["python packaging", "--source", "github-topics"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No skills found", result.output)

    def test_discover_command_accepts_org_registry_source(self):
        with mock.patch("skillsmith.commands.discover.discover_skills", return_value=[]):
            result = self.runner.invoke(discover_command, ["python packaging", "--source", "org-registry"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No skills found", result.output)

    def test_add_rejects_unpinned_github_url_by_default(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])

            result = self.runner.invoke(add_command, ["https://github.com/example/repo/tree/main/direct-skill"])

            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("require_pinned_github_refs", result.output)
            download.assert_not_called()
            self.assertFalse((cwd / "skills.lock.json").exists())

    def test_add_allows_unpinned_github_url_when_profile_disables_pin_requirement(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.add.download_github_dir") as download:
            self.runner.invoke(main, ["init", "--minimal"])
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_path.write_text(
                profile_text.replace("require_pinned_github_refs: true", "require_pinned_github_refs: false"),
                encoding="utf-8",
            )

            def fake_download(url, target):
                target.mkdir(parents=True, exist_ok=True)
                (target / "SKILL.md").write_text(
                    "---\nname: direct-skill\ndescription: test\nversion: 1.0.0\n---\nbody",
                    encoding="utf-8",
                )

            download.side_effect = fake_download
            result = self.runner.invoke(add_command, ["https://github.com/example/repo/tree/main/direct-skill"])

            self.assertEqual(result.exit_code, 0, result.output)
            download.assert_called_once()
            self.assertTrue((cwd / "skills.lock.json").exists())

    def test_recommend_command_renders_preview_with_reasons(self):
        candidate = SkillCandidate(
            name="python_packaging",
            description="Package and publish Python libraries",
            source="local",
            trust_score=95,
            install_ref="python_packaging",
            metadata={"starter_pack": True, "starter_pack_label": "library:pytest"},
        )
        explanation = {
            "reasons": ["starter pack:library:pytest", "query:python"],
            "matched_query": ["python"],
            "matched_profile": ["pytest"],
        }
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.recommend.explain_recommendations_for_profile",
            return_value=[(candidate, explanation)],
        ):
            self.runner.invoke(main, ["init", "--minimal"])
            result = self.runner.invoke(main, ["recommend"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Recommended Skills", result.output)
        self.assertIn("python_pa", result.output)
        self.assertIn("Package", result.output)
        self.assertIn("libraries", result.output)
        self.assertIn("starter", result.output)
        self.assertIn("Why", result.output)

    def test_profile_set_and_show_preserves_unknown_keys(self):
        with self.project_dir() as cwd:
            self.runner.invoke(main, ["init", "--minimal"])

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_path.write_text(profile_path.read_text(encoding="utf-8") + "custom_note: keep-me\n", encoding="utf-8")

            result = self.runner.invoke(
                main,
                [
                    "profile",
                    "set",
                    "--target-tools",
                    "claude,cursor",
                    "--priorities",
                    "speed,maintainability",
                    "--trusted-skill-sources",
                    "local,github",
                    "--min-remote-trust-score",
                    "82",
                    "--blocked-skill-sources",
                    "github,gitlab",
                    "--allow-unpinned-github-refs",
                    "--min-remote-freshness-score",
                    "11",
                    "--required-remote-licenses",
                    "MIT,Apache-2.0",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            profile_text = profile_path.read_text(encoding="utf-8")
            self.assertIn("custom_note: keep-me", profile_text)
            self.assertIn("claude", profile_text)
            self.assertIn("cursor", profile_text)
            self.assertIn("min_remote_trust_score: 82", profile_text)
            self.assertIn("blocked_skill_sources:", profile_text)
            self.assertIn("gitlab", profile_text)
            self.assertIn("require_pinned_github_refs: false", profile_text)
            self.assertIn("min_remote_freshness_score: 11", profile_text)
            self.assertIn("required_remote_licenses:", profile_text)
            self.assertIn("Apache-2.0", profile_text)
            self.assertIn("require_pinned_github_refs=False", result.output)
            self.assertIn("blocked_skill_sources=", result.output)
            self.assertIn("min_remote_freshness_score=11", result.output)
            self.assertIn("required_remote_licenses=", result.output)

            show_result = self.runner.invoke(main, ["profile", "show"])
            self.assertEqual(show_result.exit_code, 0, show_result.output)
            self.assertIn("Project Profile", show_result.output)
            self.assertIn("custom_note: keep-me", show_result.output)
            self.assertIn("target_tools:", show_result.output)
            self.assertIn("claude", show_result.output)
            self.assertIn("blocked_skill_sources:", show_result.output)
            self.assertIn("min_remote_freshness_score: 11", show_result.output)
            self.assertIn("required_remote_licenses:", show_result.output)

    def test_profile_set_sync_preserves_new_remote_policy_fields(self):
        with self.project_dir() as cwd:
            self.runner.invoke(main, ["init", "--minimal"])

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_path.write_text(
                profile_path.read_text(encoding="utf-8")
                + "custom_note: keep-me\n"
                + "blocked_skill_sources:\n"
                + "- github\n"
                + "require_pinned_github_refs: true\n"
                + "min_remote_freshness_score: 9\n"
                + "required_remote_licenses:\n"
                + "- MIT\n",
                encoding="utf-8",
            )

            result = self.runner.invoke(
                main,
                [
                    "profile",
                    "set",
                    "--target-tools",
                    "claude",
                    "--blocked-skill-sources",
                    "gitlab,github",
                    "--allow-unpinned-github-refs",
                    "--min-remote-freshness-score",
                    "13",
                    "--required-remote-licenses",
                    "Apache-2.0,MIT",
                    "--sync",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            profile_text = profile_path.read_text(encoding="utf-8")
            self.assertIn("custom_note: keep-me", profile_text)
            self.assertIn("blocked_skill_sources:", profile_text)
            self.assertIn("- gitlab", profile_text)
            self.assertIn("require_pinned_github_refs: false", profile_text)
            self.assertIn("min_remote_freshness_score: 13", profile_text)
            self.assertIn("required_remote_licenses:", profile_text)
            self.assertIn("Apache-2.0", profile_text)

    def test_profile_set_triggers_align_and_sync_hooks(self):
        with self.project_dir() as cwd:
            self.runner.invoke(main, ["init", "--minimal"])

            with mock.patch("skillsmith.commands.profile.render_all") as render_all, mock.patch(
                "skillsmith.commands.profile._sync_profile_preserving_overrides",
                return_value={"target_tools": ["claude"], "priorities": ["speed"], "trusted_skill_sources": ["local"], "min_remote_trust_score": 65},
            ) as sync_hook:
                align_result = self.runner.invoke(main, ["profile", "set", "--target-tools", "claude", "--align"])
                self.assertEqual(align_result.exit_code, 0, align_result.output)
                render_all.assert_called_once()
                sync_hook.assert_not_called()

            with mock.patch("skillsmith.commands.profile.render_all") as render_all, mock.patch(
                "skillsmith.commands.profile._sync_profile_preserving_overrides",
                return_value={"target_tools": ["claude"], "priorities": ["speed"], "trusted_skill_sources": ["local"], "min_remote_trust_score": 65},
            ) as sync_hook:
                sync_result = self.runner.invoke(main, ["profile", "set", "--priorities", "automation", "--sync"])
                self.assertEqual(sync_result.exit_code, 0, sync_result.output)
                sync_hook.assert_called_once()
                render_all.assert_not_called()

    def test_rank_candidates_prefers_profile_fit(self):
        candidates = [
            SkillCandidate(name="generic-workflow", description="general workflow", source="local", tags=["workflow"], trust_score=90),
            SkillCandidate(name="fastapi-testing", description="fastapi python backend testing", source="skills.sh", tags=["fastapi", "python"], trust_score=70),
        ]
        ranked = rank_candidates(candidates, "testing", {"languages": ["python"], "frameworks": ["fastapi"]})
        self.assertEqual(ranked[0].name, "fastapi-testing")

    def test_rank_candidates_prefers_library_packaging_for_library_profile(self):
        candidates = [
            SkillCandidate(
                name="python-packaging",
                description="Package publish and release Python libraries",
                source="skills.sh",
                tags=["python", "packaging"],
                trust_score=70,
            ),
            SkillCandidate(
                name="frontend-ui-review",
                description="Review browser UI flows",
                source="local",
                tags=["frontend", "react"],
                trust_score=90,
            ),
        ]
        profile = {
            "app_type": "library",
            "languages": ["python"],
            "frameworks": ["pytest"],
            "priorities": ["testability", "verification"],
            "target_tools": ["claude"],
        }

        ranked = rank_candidates(candidates, "starter skills", profile)

        self.assertEqual(ranked[0].name, "python-packaging")

    def test_rank_candidates_prefers_tool_compatible_workflow_for_fullstack_profile(self):
        candidates = [
            SkillCandidate(
                name="claude-fullstack-workflows",
                description="Fullstack workflow automation for Claude and Cursor",
                source="skills.sh",
                tags=["fullstack", "workflow", "claude", "cursor"],
                compatibility=["claude", "cursor"],
                trust_score=70,
            ),
            SkillCandidate(
                name="generic-docs",
                description="General writing skill",
                source="local",
                tags=["docs"],
                trust_score=90,
            ),
        ]
        profile = {
            "app_type": "fullstack-app",
            "languages": ["python", "typescript"],
            "frameworks": ["fastapi", "next"],
            "priorities": ["automation", "speed"],
            "target_tools": ["claude", "cursor"],
        }

        ranked = rank_candidates(candidates, "recommended skills", profile)

        self.assertEqual(ranked[0].name, "claude-fullstack-workflows")

    def test_recommend_skills_for_profile_builds_query_from_profile_shape(self):
        profile = {
            "app_type": "fullstack-app",
            "languages": ["python", "typescript"],
            "frameworks": ["fastapi", "next"],
            "priorities": ["automation", "speed"],
            "target_tools": ["claude", "cursor"],
            "build_commands": ["npm run build"],
            "test_commands": ["pytest"],
            "allow_remote_skills": False,
        }
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.providers.discover_skills", return_value=[]) as discover:
            recommend_skills_for_profile(profile, cwd, limit=4)

            discover.assert_called_once()
            query = discover.call_args.args[0]
            self.assertIn("fullstack-app", query)
            self.assertIn("fastapi", query)
            self.assertIn("cursor", query)
            self.assertIn("pytest", query)

    def test_curated_pack_candidates_match_library_profile(self):
        catalog = [
            {"name": "agentic_workflow", "description": "workflow", "tags": ["workflow"]},
            {"name": "software_architecture", "description": "architecture", "tags": ["architecture"]},
            {"name": "verification_before_completion", "description": "verify", "tags": ["verify"]},
            {"name": "python_packaging", "description": "package python libraries", "tags": ["python", "packaging"]},
            {"name": "python_testing_patterns", "description": "testing", "tags": ["python", "testing"]},
            {"name": "uv_package_manager", "description": "uv", "tags": ["uv", "python"]},
        ]
        profile = {
            "app_type": "library",
            "languages": ["python"],
            "frameworks": ["pytest"],
            "package_manager": "uv",
        }
        with mock.patch("skillsmith.commands.providers.load_catalog", return_value=catalog):
            candidates = curated_pack_candidates(profile, limit=6)

        names = [candidate.name for candidate in candidates]
        self.assertIn("python_packaging", names)
        self.assertIn("python_testing_patterns", names)
        self.assertIn("uv_package_manager", names)

    def test_explain_candidate_includes_starter_pack_and_signal_reasons(self):
        candidate = SkillCandidate(
            name="python_packaging",
            description="Package publish and release Python libraries",
            source="local",
            trust_score=95,
            freshness_score=8,
            compatibility=["claude"],
            metadata={"starter_pack": True, "starter_pack_label": "library:pytest"},
        )
        profile = {
            "app_type": "library",
            "languages": ["python"],
            "frameworks": ["pytest"],
            "target_tools": ["claude"],
            "priorities": ["testability"],
        }

        explanation = explain_candidate(candidate, "python packaging", profile)

        joined = " | ".join(explanation["reasons"])
        self.assertIn("starter pack:library:pytest", joined)
        self.assertIn("query:", joined)
        self.assertIn("profile:", joined)

    def test_sync_refreshes_inferred_fields_but_preserves_policy(self):
        with self.project_dir() as cwd:
            self.runner.invoke(main, ["init", "--minimal"])

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("allow_remote_skills: false", "allow_remote_skills: true")
            profile_text = profile_text.replace("- local", "- local\n- skills.sh")
            profile_text = profile_text.replace("min_remote_trust_score: 65", "min_remote_trust_score: 80")
            profile_path.write_text(profile_text, encoding="utf-8")

            (cwd / "pyproject.toml").write_text("[project]\ndependencies=['fastapi','pytest']\n", encoding="utf-8")
            (cwd / "package.json").write_text(
                json.dumps({"name": "web-app", "dependencies": {"next": "14.0.0"}, "scripts": {"build": "next build", "test": "vitest"}}),
                encoding="utf-8",
            )
            (cwd / "vercel.json").write_text("{}", encoding="utf-8")
            (cwd / ".cursor").mkdir(exist_ok=True)

            result = self.runner.invoke(main, ["sync"])

            self.assertEqual(result.exit_code, 0, result.output)
            profile_text = profile_path.read_text(encoding="utf-8")
            context_text = (cwd / ".agent" / "context" / "project-context.md").read_text(encoding="utf-8")
            self.assertIn("app_type: fullstack-app", profile_text)
            self.assertIn("deployment_target: vercel", profile_text)
            self.assertIn("allow_remote_skills: true", profile_text)
            self.assertIn("min_remote_trust_score: 80", profile_text)
            self.assertIn("- cursor", context_text)

    def test_sync_auto_install_prints_recommendation_reasons(self):
        candidate = SkillCandidate(
            name="atomic_execution",
            description="Atomic execution workflow",
            source="local",
            install_ref="atomic_execution",
            trust_score=90,
            metadata={"recommendation": {"reasons": ["starter pack:library:pytest", "query:python"]}},
        )
        explanation = {
            "reasons": ["starter pack:library:pytest", "query:python"],
            "matched_query": ["python"],
            "matched_profile": ["pytest"],
        }
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.init.explain_recommendations_for_profile", return_value=[(candidate, explanation)]
        ):
            self.runner.invoke(main, ["init", "--minimal"])
            result = self.runner.invoke(main, ["sync", "--auto-install"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Installed recommended skills", result.output)
            self.assertIn("starter pack", result.output)
            lockfile = json.loads((cwd / "skills.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lockfile["skills"][0]["name"], "atomic_execution")
            self.assertIn("recommendation", lockfile["skills"][0])

    def test_skills_sh_provider_normalizes_remote_payload(self):
        response = mock.Mock()
        response.json.return_value = {
            "skills": [
                {
                    "name": "python-packaging",
                    "description": "Package and publish Python libraries",
                    "version": "1.2.0",
                    "category": "python",
                    "topics": ["python", "packaging"],
                    "license": "MIT",
                    "maintainer": "Acme Platform Team",
                    "owner": "wshobson",
                    "repo": "agents",
                    "created_at": "2026-03-10T00:00:00Z",
                    "weekly_installs": 120,
                }
            ]
        }
        response.raise_for_status.return_value = None

        with mock.patch("skillsmith.commands.providers.requests.get", return_value=response), mock.patch(
            "skillsmith.commands.providers._freshness_from_timestamp", return_value=11
        ) as freshness:
            results = SkillsShProvider().search("python packaging", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "python-packaging")
        self.assertEqual(results[0].source, "skills.sh")
        self.assertIn("wshobson", results[0].install_ref)
        self.assertEqual(results[0].tags, ["python", "packaging"])
        self.assertEqual(results[0].metadata["license"], "MIT")
        self.assertEqual(results[0].metadata["maintainer"], "Acme Platform Team")
        self.assertEqual(results[0].metadata["freshness_source"], "created_at")
        self.assertEqual(results[0].freshness_score, 11)
        freshness.assert_called_once_with("2026-03-10T00:00:00Z")

    def test_huggingface_provider_normalizes_dict_payload(self):
        response = mock.Mock()
        response.json.return_value = {
            "spaces": [
                {
                    "id": "acme/skill-space",
                    "description": "Package and publish Python libraries",
                    "cardData": {
                        "license": "Apache-2.0",
                        "maintainer": "Acme AI",
                        "topics": ["python", "packaging"],
                    },
                    "sdk": "gradio",
                    "lastModified": "2026-03-11T00:00:00Z",
                    "likes": 44,
                }
            ]
        }
        response.raise_for_status.return_value = None

        with mock.patch("skillsmith.commands.providers.requests.get", return_value=response), mock.patch(
            "skillsmith.commands.providers._freshness_from_timestamp", return_value=10
        ) as freshness:
            results = HuggingFaceProvider().search("python packaging", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "acme/skill-space")
        self.assertEqual(results[0].source, "huggingface")
        self.assertEqual(results[0].install_ref, "acme/skill-space")
        self.assertEqual(results[0].tags, ["python", "packaging"])
        self.assertEqual(results[0].metadata["license"], "Apache-2.0")
        self.assertEqual(results[0].metadata["maintainer"], "Acme AI")
        self.assertEqual(results[0].metadata["freshness_source"], "lastModified")
        self.assertEqual(results[0].freshness_score, 10)
        freshness.assert_called_once_with("2026-03-11T00:00:00Z")

    def test_huggingface_provider_normalizes_list_payload(self):
        response = mock.Mock()
        response.json.return_value = [
            {
                "id": "acme/cli-helper",
                "name": "cli-helper",
                "description": "CLI automation helper",
                "license": "MIT",
                "author": "Acme AI",
                "tags": ["cli", "automation"],
                "createdAt": "2026-03-05T00:00:00Z",
                "downloads": 123,
                "space_sdk": "streamlit",
            }
        ]
        response.raise_for_status.return_value = None

        with mock.patch("skillsmith.commands.providers.requests.get", return_value=response), mock.patch(
            "skillsmith.commands.providers._freshness_from_timestamp", return_value=9
        ) as freshness:
            results = HuggingFaceProvider().search("cli automation", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "acme/cli-helper")
        self.assertEqual(results[0].source, "huggingface")
        self.assertEqual(results[0].category, "streamlit")
        self.assertEqual(results[0].tags, ["cli", "automation"])
        self.assertEqual(results[0].metadata["license"], "MIT")
        self.assertEqual(results[0].metadata["maintainer"], "Acme AI")
        self.assertEqual(results[0].metadata["freshness_source"], "createdAt")
        freshness.assert_called_once_with("2026-03-05T00:00:00Z")

    def test_github_topics_provider_normalizes_search_payload(self):
        response = mock.Mock()
        response.json.return_value = {
            "items": [
                {
                    "full_name": "acme/skill-index",
                    "html_url": "https://github.com/acme/skill-index",
                    "description": "GitHub topics index",
                    "topics": ["python", "packaging"],
                    "owner": {"login": "acme"},
                    "license": {"spdx_id": "MIT", "name": "MIT License"},
                    "language": "Python",
                    "stargazers_count": 42,
                    "updated_at": "2026-03-12T00:00:00Z",
                }
            ]
        }
        response.raise_for_status.return_value = None

        with mock.patch("skillsmith.commands.providers.requests.get", return_value=response) as get, mock.patch(
            "skillsmith.commands.providers._freshness_from_timestamp", return_value=12
        ) as freshness:
            results = GitHubTopicsProvider().search("python packaging", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "acme/skill-index")
        self.assertEqual(results[0].source, "github-topics")
        self.assertEqual(results[0].install_ref, "https://github.com/acme/skill-index")
        self.assertEqual(results[0].tags, ["python", "packaging"])
        self.assertEqual(results[0].metadata["license"], "MIT")
        self.assertEqual(results[0].metadata["maintainer"], "acme")
        self.assertEqual(results[0].metadata["github_url"], "https://github.com/acme/skill-index")
        self.assertEqual(results[0].metadata["freshness_source"], "updated_at")
        self.assertEqual(results[0].freshness_score, 12)
        freshness.assert_called_once_with("2026-03-12T00:00:00Z")
        get.assert_called_once()
        self.assertIn("topic:skills", get.call_args.kwargs["params"]["q"])

    def test_org_registry_provider_normalizes_registry_payload(self):
        with self.project_dir() as cwd:
            registry_path = cwd / ".agent" / "registry"
            registry_path.mkdir(parents=True, exist_ok=True)
            (registry_path / "skills.json").write_text(
                json.dumps(
                    {
                        "skills": [
                            {
                                "name": "registry-packaging",
                                "description": "Org approved packaging workflow",
                                "category": "python",
                                "topics": ["python", "packaging"],
                                "license_name": "Apache-2.0",
                                "maintainer": "Platform Team",
                                "url": "https://github.com/acme/registry-packaging",
                                "path": "skills/registry-packaging",
                                "updated_at": "2026-03-13T00:00:00Z",
                                "installs": 55,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("skillsmith.commands.providers._freshness_from_timestamp", return_value=13):
                results = OrgRegistryProvider().search("packaging", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "registry-packaging")
        self.assertEqual(results[0].source, "org-registry")
        self.assertEqual(results[0].install_ref, "https://github.com/acme/registry-packaging")
        self.assertEqual(results[0].tags, ["python", "packaging"])
        self.assertEqual(results[0].metadata["license"], "Apache-2.0")
        self.assertEqual(results[0].metadata["maintainer"], "Platform Team")
        self.assertEqual(results[0].metadata["freshness_source"], "updated_at")
        self.assertEqual(results[0].freshness_score, 13)

    def test_normalized_metadata_improves_ranking_and_explanation(self):
        response = mock.Mock()
        response.json.return_value = {
            "skills": [
                {
                    "name": "rich-metadata",
                    "description": "Package and publish Python libraries",
                    "category": "python",
                    "topics": ["python", "packaging"],
                    "license": "MIT",
                    "maintainer": "Acme Platform Team",
                    "owner": "wshobson",
                    "repo": "agents",
                    "created_at": "2026-03-10T00:00:00Z",
                    "weekly_installs": 120,
                },
                {
                    "name": "plain-skill",
                    "description": "Package and publish Python libraries",
                    "category": "python",
                    "owner": "wshobson",
                    "repo": "agents",
                    "weekly_installs": 120,
                },
            ]
        }
        response.raise_for_status.return_value = None

        with mock.patch("skillsmith.commands.providers.requests.get", return_value=response), mock.patch(
            "skillsmith.commands.providers._freshness_from_timestamp",
            side_effect=lambda value: 11 if value == "2026-03-10T00:00:00Z" else 0,
        ):
            candidates = SkillsShProvider().search("", limit=5)

        ranked = rank_candidates(candidates, "", {})
        top = ranked[0]
        explanation = explain_candidate(top, "", {})
        joined = " | ".join(explanation["reasons"])

        self.assertEqual(top.name, "rich-metadata")
        self.assertIn("license:MIT", joined)
        self.assertIn("maintainer:Acme Platform Team", joined)
        self.assertIn("freshness:created_at", joined)
        self.assertIn("metadata_bonus:+", joined)

    def test_list_renders_non_string_catalog_values(self):
        catalog = [
            {"name": "alpha", "version": 1.2, "category": 7, "description": "A" * 120, "tags": ["python"]},
        ]
        with mock.patch("skillsmith.commands.list_cmd.load_catalog", return_value=catalog):
            result = self.runner.invoke(list_command, [])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("alpha", result.output)
        self.assertIn("1.2", result.output)

    def test_list_supports_list_categories_alias(self):
        catalog = [
            {"name": "alpha", "version": "0.1.0", "category": "security", "description": "desc"},
            {"name": "beta", "version": "0.2.0", "category": "testing", "description": "desc"},
        ]
        with mock.patch("skillsmith.commands.list_cmd.load_catalog", return_value=catalog):
            result = self.runner.invoke(list_command, ["--list-categories"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("security", result.output)
        self.assertIn("testing", result.output)

    def test_lint_reports_valid_local_skill(self):
        with self.project_dir() as cwd:
            make_skill(cwd / ".agent" / "skills" / "sample_skill")

            result = self.runner.invoke(lint_command, ["--local"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("PASS", result.output)
            self.assertIn("sample_skill", result.output)

    def test_compose_writes_workflow_file(self):
        catalog = [
            {"name": "backend-testing", "description": "testing python backend", "tags": ["testing", "python"]},
            {"name": "security-audit", "description": "security review", "tags": ["security"]},
        ]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            output_path = cwd / "workflow.yml"
            result = self.runner.invoke(compose_command, ["test python backend", "--output", str(output_path)])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(output_path.exists())
            workflow = output_path.read_text(encoding="utf-8")
            self.assertIn("goal: test python backend", workflow)
            self.assertIn("backend-testing", workflow)
            self.assertIn("profile:", workflow)
            self.assertNotIn("Feedback loop:", workflow)
            self.assertIn("reflection_max_retries: 0", workflow)

    def test_compose_supports_goal_option_alias(self):
        catalog = [
            {"name": "backend-testing", "description": "testing python backend", "tags": ["testing", "python"]},
        ]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            output_path = cwd / "workflow.yml"
            result = self.runner.invoke(
                compose_command,
                ["--goal", "test python backend", "--output", str(output_path)],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertIn("goal: test python backend", workflow)
            self.assertIn("backend-testing", workflow)

    def test_compose_rejects_positional_goal_and_goal_option_together(self):
        with self.project_dir() as cwd:
            self.runner.invoke(main, ["init", "--minimal"])
            result = self.runner.invoke(
                compose_command,
                ["test python backend", "--goal", "duplicate"],
            )

            self.assertNotEqual(result.exit_code, 0, result.output)
            self.assertIn("either as positional GOAL or with --goal", result.output)

    def test_compose_supports_planner_editor_mode_with_reflection_retries(self):
        catalog = [{"name": "planner-skill", "description": "plan then implement", "tags": ["plan", "implement"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            output_path = cwd / "workflow.yml"
            result = self.runner.invoke(
                compose_command,
                [
                    "implement a feature",
                    "--mode",
                    "planner-editor",
                    "--reflection-retries",
                    "2",
                    "--output",
                    str(output_path),
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertIn("execution_mode: planner-editor", workflow)
            self.assertIn("reflection_max_retries: 2", workflow)
            self.assertIn("Planner phase:", workflow)
            self.assertIn("Editor phase:", workflow)
            self.assertIn("Reflection loop:", workflow)

    def test_compose_applies_rolling_feedback_from_recent_eval_artifacts(self):
        catalog = [{"name": "verification", "description": "test and verify changes", "tags": ["test", "verify"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            (cwd / ".agent" / "evals").mkdir(parents=True, exist_ok=True)
            (cwd / ".agent" / "evals" / "policy.json").write_text(
                json.dumps(
                    {
                        "compose": {
                            "feedback_window": 3,
                            "minimum_artifacts": 3,
                            "reflection_retry_cap": 2,
                            "verification_pass_floor": 1,
                            "verification_pass_cap": 3,
                            "tacr_floor": 75,
                            "delta_tacr_floor": 0,
                            "interventions_threshold": 2,
                            "latency_increase_threshold_ms": 0,
                            "cost_increase_threshold_usd": 0,
                            "planner_editor": {
                                "enabled": True,
                                "risk_threshold": 2,
                                "tacr_floor": 70,
                                "delta_tacr_floor": 0,
                                "interventions_threshold": 2,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-17T00-00-00Z.json",
                generated_at="2026-03-17T00:00:00Z",
                tacr=82.0,
                total_interventions=0,
                avg_latency_ms=100,
                avg_cost_usd=0.1,
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-18T00-00-00Z.json",
                generated_at="2026-03-18T00:00:00Z",
                tacr=68.0,
                total_interventions=1,
                avg_latency_ms=120,
                avg_cost_usd=0.12,
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-19T00-00-00Z.json",
                generated_at="2026-03-19T00:00:00Z",
                tacr=55.0,
                total_interventions=2,
                avg_latency_ms=140,
                avg_cost_usd=0.14,
            )
            output_path = cwd / "workflow.yml"

            result = self.runner.invoke(
                compose_command,
                ["test API changes", "--feedback-window", "3", "--output", str(output_path)],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertIn("Feedback loop:", workflow)
            self.assertIn("rolling TACR was 68.33", workflow)
            self.assertIn("delta TACR -27", workflow)
            self.assertIn("verification_passes: 3", workflow)
            self.assertIn("reflection_max_retries: 2", workflow)
            self.assertIn("mode_suggestion: planner-editor", workflow)
            self.assertIn("Planner-editor mode suggestion:", workflow)
            self.assertIn("Verification loop: run 3 verification passes", workflow)

    def test_compose_clamps_feedback_by_slo_budget_caps_and_emits_breach_metadata(self):
        catalog = [{"name": "verification", "description": "test and verify changes", "tags": ["test", "verify"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            (cwd / ".agent" / "evals").mkdir(parents=True, exist_ok=True)
            slo_budget_policy = {
                "feedback_window": 3,
                "minimum_artifacts": 3,
                "reflection_retry_cap": 3,
                "verification_pass_floor": 1,
                "verification_pass_cap": 4,
                "tacr_floor": 75,
                "delta_tacr_floor": 0,
                "interventions_threshold": 3,
                "latency_increase_threshold_ms": 0,
                "cost_increase_threshold_usd": 0,
                "planner_editor": {
                    "enabled": True,
                    "risk_threshold": 2,
                    "tacr_floor": 70,
                    "delta_tacr_floor": 0,
                    "interventions_threshold": 2,
                },
                "selected_budget_profile": "release",
                "budget_profiles": {
                    "release": {"slo_budget": "release-tight"},
                    "default": {"slo_budget": "default"},
                },
                "slo_budgets": {
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
                            "tacr_floor": 80,
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
            }
            (cwd / ".agent" / "evals" / "policy.json").write_text(json.dumps(slo_budget_policy), encoding="utf-8")
            resolved_budget_policy = {
                "selected_budget_profile": "release",
                "selected_slo_budget": "release-tight",
                "resolved_slo_budget": {
                    "name": "release-tight",
                    "selector": "budget_profiles.release.slo_budget",
                    "source": "budget_profiles.release.slo_budget",
                    "thresholds": slo_budget_policy["slo_budgets"]["release-tight"]["thresholds"],
                    "caps": slo_budget_policy["slo_budgets"]["release-tight"]["caps"],
                },
            }
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-17T00-00-00Z.json",
                generated_at="2026-03-17T00:00:00Z",
                tacr=82.0,
                total_interventions=0,
                avg_latency_ms=100,
                avg_cost_usd=0.1,
                policy=resolved_budget_policy,
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-18T00-00-00Z.json",
                generated_at="2026-03-18T00:00:00Z",
                tacr=68.0,
                total_interventions=1,
                avg_latency_ms=120,
                avg_cost_usd=0.12,
                policy=resolved_budget_policy,
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-19T00-00-00Z.json",
                generated_at="2026-03-19T00:00:00Z",
                tacr=55.0,
                total_interventions=2,
                avg_latency_ms=140,
                avg_cost_usd=0.14,
                policy=resolved_budget_policy,
            )
            feedback = load_rolling_eval_feedback(cwd, feedback_window=3)
            self.assertIsNotNone(feedback)
            assert feedback is not None
            self.assertEqual(feedback["policy"]["resolved_slo_budget"]["name"], "release-tight")
            self.assertFalse(feedback["policy"]["resolved_slo_budget"]["caps"]["allow_mode_switch"])

            workflow = build_workflow("test API changes", cwd, max_skills=3, feedback=feedback)
            self.assertEqual(workflow["verification_passes"], 2)
            self.assertEqual(workflow["reflection_max_retries"], 1)
            self.assertEqual(workflow["slo_budget"]["name"], "release-tight")
            self.assertFalse(workflow["slo_budget"]["caps"]["allow_mode_switch"])
            self.assertIn("rolling TACR 68.33% below floor 80%", " | ".join(workflow["breach_reasons"]))

            output_path = cwd / "workflow.yml"
            result = self.runner.invoke(
                compose_command,
                ["test API changes", "--feedback-window", "3", "--output", str(output_path)],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertIn("SLO budget: release-tight", workflow)
            self.assertIn("Breaches:", workflow)
            self.assertIn("verification_passes: 2", workflow)
            self.assertIn("reflection_max_retries: 1", workflow)
            self.assertNotIn("Planner-editor mode suggestion:", workflow)
            self.assertNotIn("mode_suggestion: planner-editor", workflow)

    def test_compose_ignores_feedback_when_disabled(self):
        catalog = [{"name": "verification", "description": "test and verify changes", "tags": ["test", "verify"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            write_latest_eval_artifact(cwd, tacr=55.0, total_interventions=4)
            output_path = cwd / "workflow.yml"

            result = self.runner.invoke(
                compose_command,
                ["test API changes", "--no-feedback", "--output", str(output_path)],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertNotIn("Feedback loop:", workflow)
            self.assertIn("reflection_max_retries: 0", workflow)

    def test_compose_noops_when_insufficient_feedback_artifacts(self):
        catalog = [{"name": "verification", "description": "test and verify changes", "tags": ["test", "verify"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])
            (cwd / ".agent" / "evals").mkdir(parents=True, exist_ok=True)
            (cwd / ".agent" / "evals" / "policy.json").write_text(
                json.dumps(
                    {
                        "compose": {
                            "feedback_window": 3,
                            "minimum_artifacts": 3,
                            "reflection_retry_cap": 2,
                            "verification_pass_floor": 1,
                            "verification_pass_cap": 3,
                            "planner_editor": {
                                "enabled": True,
                                "risk_threshold": 2,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-18T00-00-00Z.json",
                generated_at="2026-03-18T00:00:00Z",
                tacr=68.0,
                total_interventions=1,
                avg_latency_ms=120,
                avg_cost_usd=0.12,
            )
            write_eval_history_artifact(
                cwd,
                artifact_name="eval-2026-03-19T00-00-00Z.json",
                generated_at="2026-03-19T00:00:00Z",
                tacr=55.0,
                total_interventions=2,
                avg_latency_ms=140,
                avg_cost_usd=0.14,
            )
            output_path = cwd / "workflow.yml"

            result = self.runner.invoke(
                compose_command,
                ["test API changes", "--feedback-window", "3", "--output", str(output_path)],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            workflow = output_path.read_text(encoding="utf-8")
            self.assertNotIn("Feedback loop:", workflow)
            self.assertNotIn("mode_suggestion:", workflow)
            self.assertIn("reflection_max_retries: 0", workflow)
            self.assertIn("verification_passes: 1", workflow)

    def test_compose_writes_retrieval_trace_artifact_for_goal(self):
        fake_workflow = {
            "goal": "implement a feature",
            "skills": [{"name": "implementation"}],
            "steps": [{"name": "plan"}, {"name": "implement"}],
        }
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.compose.build_workflow",
            return_value=fake_workflow,
        ):
            self.runner.invoke(main, ["init", "--minimal"])
            output_path = cwd / "workflow.yml"
            before = snapshot_json_files(cwd)
            result = self.runner.invoke(
                compose_command,
                ["implement a feature", "--output", str(output_path)],
            )
            after = snapshot_json_files(cwd)
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(output_path.exists())
            workflow_text = output_path.read_text(encoding="utf-8")
            changed_json = {
                path: text
                for path, text in after.items()
                if before.get(path) != text and path.endswith(".json")
            }
            trace_paths = [
                path
                for path in changed_json
                if "trace" in Path(path).stem.lower() or "retrieval" in Path(path).stem.lower() or "/traces/" in path
            ]
            if trace_paths:
                trace_payload = json.loads((cwd / trace_paths[0]).read_text(encoding="utf-8"))
                self.assertEqual(trace_payload.get("goal"), "implement a feature")
                retrieval_tier = trace_payload.get("retrieval_tier", trace_payload.get("tier"))
                self.assertIn(retrieval_tier, {"l0", "l1", "l2"})
                candidates = trace_payload.get("candidates") or trace_payload.get("results") or []
                self.assertTrue(candidates, trace_payload)
            else:
                self.assertTrue(
                    "retrieval_trace:" in workflow_text or "context_trace:" in workflow_text,
                    workflow_text,
                )

    def test_build_workflow_prefers_installed_skills(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=[]):
            self.runner.invoke(main, ["init", "--minimal"])
            self.runner.invoke(add_command, ["atomic_execution"])

            workflow = build_workflow("implement a feature", cwd, max_skills=3)

            self.assertIn("atomic_execution", workflow["skills"])
            self.assertIn("Read .agent/project_profile.yaml", workflow["steps"][0])

    def test_build_workflow_adjusts_steps_for_debug_goals(self):
        catalog = [{"name": "debugging", "description": "debug and fix bugs", "tags": ["debug", "bugfix"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow("debug login bug", cwd, max_skills=3)

            step_text = " ".join(workflow["steps"])
            self.assertIn("Reproduce the issue", step_text)
            self.assertIn("Implement the fix", step_text)

    def test_build_workflow_adjusts_steps_for_brainstorm_goals(self):
        catalog = [{"name": "ideation", "description": "brainstorm architecture ideas", "tags": ["brainstorm", "design"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow("brainstorm onboarding flow", cwd, max_skills=3)

            step_text = " ".join(workflow["steps"])
            self.assertIn("2-3 credible approaches", step_text)
            self.assertIn("recommended path", step_text)

    def test_build_workflow_adjusts_steps_for_test_goals(self):
        catalog = [{"name": "verification", "description": "test and verify changes", "tags": ["test", "verify"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow("test API changes", cwd, max_skills=3)

            step_text = " ".join(workflow["steps"])
            self.assertIn("highest-risk behavior", step_text)
            self.assertIn("automated tests", step_text)

    def test_build_workflow_adjusts_steps_for_deploy_goals(self):
        catalog = [{"name": "release-readiness", "description": "deploy and release checklist", "tags": ["deploy", "release"]}]
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow("deploy release", cwd, max_skills=3)

            step_text = " ".join(workflow["steps"])
            self.assertIn("release readiness", step_text)
            self.assertIn("rollback notes", step_text)

    def test_build_workflow_supports_planner_editor_mode(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=[]):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow(
                "implement a feature",
                cwd,
                max_skills=3,
                execution_mode="planner-editor",
            )

            step_text = " ".join(workflow["steps"])
            self.assertEqual(workflow["execution_mode"], "planner-editor")
            self.assertEqual(workflow["reflection_max_retries"], 0)
            self.assertIn("Planner phase:", step_text)
            self.assertIn("Editor phase:", step_text)

    def test_build_workflow_adds_reflection_loop_when_retries_enabled(self):
        with self.project_dir() as cwd, mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=[]):
            self.runner.invoke(main, ["init", "--minimal"])

            workflow = build_workflow(
                "implement a feature",
                cwd,
                max_skills=3,
                reflection_max_retries=2,
            )

            step_text = " ".join(workflow["steps"])
            self.assertEqual(workflow["execution_mode"], "standard")
            self.assertEqual(workflow["reflection_max_retries"], 2)
            self.assertIn("Reflection loop:", step_text)

    def test_doctor_flags_missing_files(self):
        with self.project_dir():
            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value=None):
                result = self.runner.invoke(doctor_command, [])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("AGENTS.md missing", result.output)
        self.assertIn(".agent/PROJECT.md missing", result.output)

    def test_doctor_detects_render_drift(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            (cwd / "AGENTS.md").write_text("drifted", encoding="utf-8")

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("AGENTS.md is out of sync", result.output)

    def test_doctor_reports_lockfile(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            self.runner.invoke(add_command, ["atomic_execution"])

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("skills.lock.json", result.output)

    def test_doctor_flags_unsigned_lockfile_when_signing_key_is_set(self):
        with self.project_dir() as cwd, mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "doctor-secret"}, clear=False
        ):
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            (cwd / "skills.lock.json").write_text(
                json.dumps({"version": 1, "schema_version": 2, "skills": []}),
                encoding="utf-8",
            )

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("signature missing", result.output)

    def test_doctor_strict_exits_non_zero_on_warnings(self):
        with self.project_dir():
            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value=None):
                result = self.runner.invoke(doctor_command, ["--strict"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Some issues found", result.output)

    def test_doctor_detects_checksum_mismatch_for_local_skill(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            add_result = self.runner.invoke(add_command, ["atomic_execution"])
            self.assertEqual(add_result.exit_code, 0, add_result.output)

            skill_file = cwd / ".agent" / "skills" / "atomic_execution" / "SKILL.md"
            skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nTampered\n", encoding="utf-8")

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("checksum mismatch", result.output)
            self.assertIn("atomic_execution", result.output)

    def test_doctor_reports_lockfile_recommendation_rationale(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            skill_dir = cwd / ".agent" / "skills" / "python-packaging"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("body", encoding="utf-8")
            lockfile = {
                "version": 1,
                "skills": [
                    {
                        "name": "python-packaging",
                        "source": "skills.sh",
                        "version": "1.2.0",
                        "install_ref": "wshobson/agents/python-packaging",
                        "trust_score": 70,
                        "category": "python",
                        "tags": ["python"],
                        "installed_at": "2026-02-21T00:00:00Z",
                        "path": ".agent/skills/python-packaging",
                        "checksum": "abc123",
                        "metadata": {},
                        "recommendation": {
                            "starter_pack": "python-library",
                            "reasons": ["starter pack match", "query fit"],
                            "matched_query": ["python"],
                            "matched_profile": ["pytest", "packaging"],
                        },
                    }
                ],
            }
            (cwd / "skills.lock.json").write_text(json.dumps(lockfile), encoding="utf-8")

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Recommendation Rationale", result.output)
            self.assertIn("python-packaging", result.output)
            self.assertIn("starter pack: python-library", result.output)
            self.assertIn("reasons: starter pack match, query fit", result.output)

    def test_doctor_groups_workflow_surfaces_and_flags_remote_policy_drift(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            lockfile = {
                "version": 1,
                "skills": [
                    {
                        "name": "python-packaging",
                        "source": "skills.sh",
                        "version": "1.2.0",
                        "install_ref": "wshobson/agents/python-packaging",
                        "trust_score": 70,
                        "category": "python",
                        "tags": ["python"],
                        "installed_at": "2026-02-21T00:00:00Z",
                        "path": ".agent/skills/python-packaging",
                        "checksum": "abc123",
                        "metadata": {},
                    }
                ],
            }
            (cwd / "skills.lock.json").write_text(json.dumps(lockfile), encoding="utf-8")
            (cwd / ".agent" / "skills" / "python-packaging").mkdir(parents=True, exist_ok=True)
            (cwd / ".agent" / "skills" / "python-packaging" / "SKILL.md").write_text("body", encoding="utf-8")

            with mock.patch("skillsmith.commands.doctor.shutil.which", return_value="skillsmith"):
                result = self.runner.invoke(doctor_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Workflow Surfaces", result.output)
            self.assertIn("claude", result.output)
            self.assertIn("cursor", result.output)
            self.assertIn("remote but allow_remote_skills is disabled", result.output)

    def test_report_summarizes_profile_starter_pack_lockfile_policy_and_drift(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_text = profile_path.read_text(encoding="utf-8")
            profile_text = profile_text.replace("allow_remote_skills: false", "allow_remote_skills: true")
            profile_text = profile_text.replace("trusted_skill_sources:\n- local", "trusted_skill_sources:\n- local\n- github")
            profile_text = profile_text.replace("min_remote_trust_score: 65", "min_remote_trust_score: 80")
            profile_path.write_text(profile_text, encoding="utf-8")

            skill_dir = cwd / ".agent" / "skills" / "python-packaging"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: python-packaging\n"
                "description: Package and publish Python libraries\n"
                "version: 1.0.0\n"
                "---\n"
                "body\n",
                encoding="utf-8",
            )
            lockfile = {
                "version": 1,
                "skills": [
                    {
                        "name": "python-packaging",
                        "source": "skills.sh",
                        "version": "1.2.0",
                        "install_ref": "wshobson/agents/python-packaging",
                        "trust_score": 70,
                        "category": "python",
                        "tags": ["python", "packaging"],
                        "installed_at": "2026-02-21T00:00:00Z",
                        "path": ".agent/skills/python-packaging",
                        "checksum": "abc123",
                        "metadata": {},
                        "recommendation": {
                            "starter_pack": "python-library",
                            "reasons": ["starter pack match", "query fit"],
                            "matched_query": ["python"],
                            "matched_profile": ["pytest", "packaging"],
                        },
                    }
                ],
            }
            (cwd / "skills.lock.json").write_text(json.dumps(lockfile), encoding="utf-8")
            (cwd / "AGENTS.md").write_text("drifted", encoding="utf-8")
            write_eval_policy_fixture(cwd)
            write_context_index_fixture(cwd)
            write_registry_fixture(cwd)

            candidate = SkillCandidate(
                name="python-packaging",
                description="Package and publish Python libraries",
                source="local",
                install_ref="python-packaging",
                trust_score=95,
                metadata={"starter_pack": True, "starter_pack_label": "library:python"},
            )
            with mock.patch.dict(os.environ, {"CI": "true"}, clear=False), mock.patch(
                "skillsmith.commands.report.curated_pack_candidates", return_value=[candidate]
            ), mock.patch(
                "skillsmith.commands.report.curated_pack_label", return_value="library:python"
            ):
                result = self.runner.invoke(main, ["report"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skillsmith Report", result.output)
            self.assertIn("Profile source: saved", result.output)
            self.assertIn("Selected Starter Pack (library:python)", result.output)
            self.assertIn("python-packaging", result.output)
            self.assertIn("starter pack", result.output)
            self.assertIn("python-library", result.output)
            self.assertIn("Remote Policy", result.output)
            self.assertIn("enabled", result.output)
            self.assertIn("github", result.output)
            self.assertIn("Eval Policy", result.output)
            self.assertIn("release", result.output)
            self.assertIn("min_tacr_delta=7", result.output)
            self.assertIn("Context Index Freshness", result.output)
            self.assertIn("File count", result.output)
            self.assertIn("Stale files", result.output)
            self.assertIn("Registry Governance", result.output)
            self.assertIn("Approval pending", result.output)
            self.assertIn("deprecated-skill:set-state@2026-03-19T08:30:00Z", result.output)
            self.assertIn("AGENTS.md is out of sync", result.output)
            self.assertIn("Quick Drift Snapshot", result.output)

    def test_report_json_includes_eval_policy_context_index_and_registry_governance(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            write_eval_policy_fixture(cwd)
            write_context_index_fixture(cwd)
            write_registry_fixture(cwd)

            candidate = SkillCandidate(
                name="python-packaging",
                description="Package and publish Python libraries",
                source="local",
                install_ref="python-packaging",
                trust_score=95,
                metadata={"starter_pack": True, "starter_pack_label": "library:python"},
            )
            with mock.patch.dict(os.environ, {"CI": "true"}, clear=False), mock.patch(
                "skillsmith.commands.report.curated_pack_candidates", return_value=[candidate]
            ), mock.patch(
                "skillsmith.commands.report.curated_pack_label", return_value="library:python"
            ):
                result = self.runner.invoke(main, ["report", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["eval_policy"]["selected_budget_profile"], "release")
        self.assertEqual(payload["eval_policy"]["ci_enforcement_state"], "enabled")
        self.assertEqual(payload["eval_policy"]["effective_thresholds"]["min_tacr_delta"], 7)
        self.assertEqual(payload["context_index_freshness"]["file_count"], 3)
        self.assertEqual(payload["context_index_freshness"]["stale_count"], 1)
        self.assertEqual(payload["registry_governance"]["approval_pending_count"], 1)
        self.assertEqual(payload["registry_governance"]["deprecated_count"], 1)
        self.assertEqual(payload["registry_governance"]["recent_history_events"][0]["name"], "approved-skill")
        self.assertEqual(payload["registry_governance"]["recent_history_events"][0]["action"], "approve")

    def test_report_infers_profile_and_handles_missing_lockfile(self):
        with self.project_dir() as cwd:
            (cwd / "pyproject.toml").write_text(
                "[project]\nname='report-demo'\ndependencies=['click']\n",
                encoding="utf-8",
            )
            (cwd / "src").mkdir()
            (cwd / "tests").mkdir()

            candidate = SkillCandidate(
                name="python-testing",
                description="Testing patterns for Python",
                source="local",
                install_ref="python-testing",
                trust_score=95,
                metadata={"starter_pack": True, "starter_pack_label": "library:python"},
            )
            with mock.patch(
                "skillsmith.commands.report.curated_pack_candidates", return_value=[candidate]
            ), mock.patch(
                "skillsmith.commands.report.curated_pack_label", return_value="library:python"
            ):
                result = self.runner.invoke(main, ["report"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Profile source: inferred", result.output)
            self.assertIn("Selected Starter Pack (library:python)", result.output)
            self.assertIn("AGENTS.md missing", result.output)
            self.assertIn("skills.lock.json not found", result.output)

    def test_report_shows_lockfile_signature_status_when_signing_key_is_set(self):
        with self.project_dir() as cwd, mock.patch.dict(
            os.environ, {"SKILLSMITH_LOCKFILE_SIGNING_KEY": "report-secret"}, clear=False
        ):
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            (cwd / "skills.lock.json").write_text(
                json.dumps({"version": 1, "schema_version": 2, "skills": []}),
                encoding="utf-8",
            )

            result = self.runner.invoke(report_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("signature missing", result.output)

    def test_report_surfaces_trust_health(self):
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

            skill_dir = cwd / ".agent" / "skills" / "remote_signed"
            write_signed_remote_skill(skill_dir)
            verification = verify_remote_skill_artifact(
                skill_dir,
                {"trusted_publisher_keys": {"publisher-demo": "publisher-secret"}, "publisher_verification_mode": "required"},
                cwd=cwd,
            )
            self.assertEqual(verification["state"], "revoked")

            result = self.runner.invoke(report_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Trust Health", result.output)
            self.assertIn("Revocation file", result.output)
            self.assertIn("Transparency log", result.output)
            self.assertIn("Log entries", result.output)
            self.assertIn("publisher-demo", result.output)

    def test_budget_succeeds_with_ascii_separator(self):
        with self.project_dir() as cwd:
            (cwd / "AGENTS.md").write_text("agent rules", encoding="utf-8")
            (cwd / ".agent").mkdir()
            (cwd / ".agent" / "PROJECT.md").write_text("project", encoding="utf-8")
            (cwd / ".agent" / "ROADMAP.md").write_text("roadmap", encoding="utf-8")
            (cwd / ".agent" / "STATE.md").write_text("state", encoding="utf-8")
            make_skill(cwd / ".agent" / "skills" / "budget_skill")

            result = self.runner.invoke(budget_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("TOTAL estimated context tokens", result.output)
            self.assertIn("----------------------------------------", result.output)

    def test_update_skips_modified_skill_without_force(self):
        template_dir = find_template_skill_dir("atomic_execution")
        self.assertIsNotNone(template_dir)

        with self.project_dir() as cwd:
            target = cwd / ".agent" / "skills" / "atomic_execution"
            shutil.copytree(template_dir, target)
            skill_file = target / "SKILL.md"
            original = skill_file.read_text(encoding="utf-8")
            skill_file.write_text(downgrade_skill_version(original) + "\nLocal note\n", encoding="utf-8")

            result = self.runner.invoke(update_command, [])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("SKIP", result.output)
            self.assertIn("Local changes detected", result.output)
            self.assertIn("Local note", skill_file.read_text(encoding="utf-8"))

    def test_update_force_overwrites_modified_skill(self):
        template_dir = find_template_skill_dir("atomic_execution")
        self.assertIsNotNone(template_dir)

        with self.project_dir() as cwd:
            target = cwd / ".agent" / "skills" / "atomic_execution"
            shutil.copytree(template_dir, target)
            skill_file = target / "SKILL.md"
            original = skill_file.read_text(encoding="utf-8")
            skill_file.write_text(downgrade_skill_version(original) + "\nLocal note\n", encoding="utf-8")

            result = self.runner.invoke(update_command, ["--force"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("UPDATED", result.output)
            self.assertNotIn("Local note", skill_file.read_text(encoding="utf-8"))

    def test_rebuild_creates_catalog_from_skill_directory(self):
        with self.project_dir() as cwd:
            skill_root = cwd / "skills"
            make_skill(skill_root / "category_a" / "rebuilt_skill")
            output_path = cwd / "catalog.json"

            result = self.runner.invoke(rebuild_command, ["--dir", str(skill_root), "--output", str(output_path)])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(output_path.exists())
            catalog = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(catalog[0]["name"], "rebuilt_skill")
            self.assertEqual(catalog[0]["category"], "category_a")

    def test_serve_delegates_to_run_server(self):
        with mock.patch("skillsmith.mcp_server.run_server") as run_server:
            result = self.runner.invoke(serve_command, ["--transport", "http", "--host", "127.0.0.1", "--port", "47731"])

        self.assertEqual(result.exit_code, 0, result.output)
        run_server.assert_called_once_with("http", "127.0.0.1", 47731)

    def test_snapshot_saves_lists_and_restores(self):
        with self.project_dir() as cwd:
            state_dir = cwd / ".agent"
            state_dir.mkdir()
            state_file = state_dir / "STATE.md"
            state_file.write_text("before snapshot", encoding="utf-8")

            save_result = self.runner.invoke(snapshot_command, ["-n", "baseline"])
            self.assertEqual(save_result.exit_code, 0, save_result.output)

            snapshots = sorted((state_dir / "snapshots").glob("snap_*.zip"))
            self.assertEqual(len(snapshots), 1)
            note_files = sorted((state_dir / "snapshots").glob("*.note.txt"))
            self.assertEqual(len(note_files), 1)

            list_result = self.runner.invoke(snapshot_command, ["--list"])
            self.assertEqual(list_result.exit_code, 0, list_result.output)
            self.assertIn(snapshots[0].name, list_result.output)

            state_file.write_text("after mutation", encoding="utf-8")
            restore_result = self.runner.invoke(snapshot_command, ["--restore", snapshots[0].name])
            self.assertEqual(restore_result.exit_code, 0, restore_result.output)
            self.assertEqual(state_file.read_text(encoding="utf-8"), "before snapshot")

    def test_watch_reports_stale_state_and_stops_cleanly(self):
        with self.project_dir() as cwd:
            state_dir = cwd / ".agent"
            state_dir.mkdir()
            state_file = state_dir / "STATE.md"
            state_file.write_text("state", encoding="utf-8")
            old_time = time.time() - 7200
            os.utime(state_file, (old_time, old_time))

            with mock.patch("subprocess.check_output", return_value=b"main\n"), mock.patch(
                "skillsmith.commands.watch.time.sleep", side_effect=KeyboardInterrupt
            ):
                result = self.runner.invoke(watch_command, ["--interval", "0", "--stale-hours", "1"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("STALE", result.output)
        self.assertIn("Stopped", result.output)


if __name__ == "__main__":
    unittest.main()

