import datetime
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
from skillsmith.commands.context_index import retrieve_context_candidates


class ContextIndexCommandTests(unittest.TestCase):
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

    @staticmethod
    def fixed_timestamp(value=None):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return value.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return "2026-03-19T12:00:00Z"

    def write_index_payload(self, cwd: Path, files: list[dict]) -> None:
        context_dir = cwd / ".agent" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "generated_at": self.fixed_timestamp(),
            "freshness_stamp": self.fixed_timestamp(),
            "root": ".",
            "file_count": len(files),
            "files": files,
        }
        (context_dir / "index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_query_policy(self, cwd: Path, payload: dict) -> None:
        context_dir = cwd / ".agent" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "query_policy.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot_json_files(self, cwd: Path) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        agent_dir = cwd / ".agent"
        if not agent_dir.exists():
            return snapshot
        for path in sorted(agent_dir.rglob("*.json")):
            snapshot[path.relative_to(cwd).as_posix()] = path.read_text(encoding="utf-8")
        return snapshot

    def test_context_index_writes_freshness_stamps_and_compressed_snippets(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.context_index._timestamp_to_string",
            side_effect=self.fixed_timestamp,
        ):
            (cwd / ".agent" / "context").mkdir(parents=True)
            (cwd / "AGENTS.md").write_text(
                "# AGENTS.md\n\n   Read    the   profile   first.\n\nThen verify.\n",
                encoding="utf-8",
            )
            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_path.write_text("idea: Context index demo\npriorities:\n- verification\n", encoding="utf-8")
            readme_path = cwd / "README.md"
            readme_path.write_text("Project   README\n\nFreshness matters.\n", encoding="utf-8")

            stamp = datetime.datetime(2026, 3, 10, 8, 30, tzinfo=datetime.timezone.utc).timestamp()
            os.utime(cwd / "AGENTS.md", (stamp, stamp))
            os.utime(profile_path, (stamp, stamp))
            os.utime(readme_path, (stamp, stamp))

            with mock.patch(
                "skillsmith.commands.context_index.KEY_PROJECT_FILES",
                ["AGENTS.md", ".agent/project_profile.yaml", "README.md"],
            ):
                result = self.runner.invoke(main, ["context-index"])

            self.assertEqual(result.exit_code, 0, result.output)
            index_path = cwd / ".agent" / "context" / "index.json"
            self.assertTrue(index_path.exists())

            payload = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
            self.assertEqual(payload["file_count"], 3)
            self.assertIn("generated_at", payload)
            self.assertIn("freshness_stamp", payload)

            files = {item["path"]: item for item in payload["files"]}
            self.assertEqual(set(files), {"AGENTS.md", ".agent/project_profile.yaml", "README.md"})
            self.assertEqual(files["AGENTS.md"]["freshness_stamp"], "2026-03-10T08:30:00Z")
            self.assertEqual(files["AGENTS.md"]["path_priority_rank"], 1)
            self.assertGreater(files["AGENTS.md"]["path_priority_score"], files["README.md"]["path_priority_score"])
            self.assertNotIn("\n", files["AGENTS.md"]["compressed_snippet"])
            self.assertIn("Read the profile first.", files["AGENTS.md"]["compressed_snippet"])
            self.assertLessEqual(len(files["AGENTS.md"]["compressed_snippet"]), 240)
            self.assertGreater(files["AGENTS.md"]["freshness_score"], 0)

            self.assertIn("Context Index", result.output)
            self.assertIn(".agent/context/index.json", result.output)

    def test_context_index_query_ranks_by_lexical_match_path_priority_and_freshness(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.context_index._timestamp_to_string",
            side_effect=self.fixed_timestamp,
        ):
            (cwd / ".agent" / "context").mkdir(parents=True)
            agents_path = cwd / "AGENTS.md"
            profile_path = cwd / ".agent" / "project_profile.yaml"
            readme_path = cwd / "README.md"

            agents_path.write_text("Read the profile before anything else.\n", encoding="utf-8")
            profile_path.write_text(
                "project: retrieval demo\n"
                "profile: true\n"
                "context: project profile retrieval\n",
                encoding="utf-8",
            )
            readme_path.write_text("This readme mentions profile only once.\n", encoding="utf-8")

            agents_stamp = datetime.datetime(2026, 3, 10, 8, 30, tzinfo=datetime.timezone.utc).timestamp()
            profile_stamp = datetime.datetime(2026, 3, 15, 8, 30, tzinfo=datetime.timezone.utc).timestamp()
            readme_stamp = datetime.datetime(2026, 3, 18, 8, 30, tzinfo=datetime.timezone.utc).timestamp()
            os.utime(agents_path, (agents_stamp, agents_stamp))
            os.utime(profile_path, (profile_stamp, profile_stamp))
            os.utime(readme_path, (readme_stamp, readme_stamp))

            with mock.patch(
                "skillsmith.commands.context_index.KEY_PROJECT_FILES",
                ["AGENTS.md", ".agent/project_profile.yaml", "README.md"],
            ):
                build_result = self.runner.invoke(main, ["context-index"])
                self.assertEqual(build_result.exit_code, 0, build_result.output)
                result = self.runner.invoke(main, ["context-index", "query", "project profile", "--limit", "3"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Context Index Query", result.output)
            self.assertIn("Score", result.output)
            self.assertIn("Ranked candidates:", result.output)
            self.assertIn("path_priority=", result.output)
            self.assertLess(result.output.index("path=.agent/project_profile.yaml"), result.output.index("path=README.md"))
            self.assertLess(result.output.index("path=.agent/project_profile.yaml"), result.output.index("path=AGENTS.md"))

    def test_context_index_query_writes_retrieval_trace_artifact(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.context_index._timestamp_to_string",
            side_effect=self.fixed_timestamp,
        ):
            (cwd / ".agent" / "context").mkdir(parents=True)
            (cwd / "AGENTS.md").write_text("Read the profile before anything else.\n", encoding="utf-8")
            (cwd / ".agent" / "project_profile.yaml").write_text(
                "project: retrieval demo\nprofile: true\ncontext: project profile retrieval\n",
                encoding="utf-8",
            )
            with mock.patch(
                "skillsmith.commands.context_index.KEY_PROJECT_FILES",
                ["AGENTS.md", ".agent/project_profile.yaml"],
            ):
                self.assertEqual(self.runner.invoke(main, ["context-index"]).exit_code, 0)
                before = self.snapshot_json_files(cwd)
                result = self.runner.invoke(main, ["context-index", "query", "project profile", "--limit", "2"])

            self.assertEqual(result.exit_code, 0, result.output)
            after = self.snapshot_json_files(cwd)
            changed = {path: text for path, text in after.items() if before.get(path) != text}
            trace_paths = [
                path
                for path in changed
                if "trace" in Path(path).stem.lower() or "retrieval" in Path(path).stem.lower() or "/traces/" in path
            ]
            if not trace_paths and ".agent/context/index.json" in changed:
                index_payload = json.loads((cwd / ".agent" / "context" / "index.json").read_text(encoding="utf-8"))
                trace_payload = (
                    index_payload.get("retrieval_trace")
                    or index_payload.get("query_trace")
                    or index_payload.get("trace")
                    or index_payload.get("queries")
                )
                self.assertIsInstance(trace_payload, dict, index_payload)
                self.assertEqual(trace_payload.get("query"), "project profile")
                self.assertIn(trace_payload.get("tier"), {"l0", "l1", "l2"})
                candidates = trace_payload.get("candidates") or trace_payload.get("results") or []
                self.assertTrue(candidates, trace_payload)
            else:
                self.assertTrue(trace_paths, changed)
                trace_payload = json.loads((cwd / trace_paths[0]).read_text(encoding="utf-8"))
                self.assertEqual(trace_payload.get("query"), "project profile")
                self.assertIn(trace_payload.get("tier"), {"l0", "l1", "l2"})
                candidates = trace_payload.get("candidates") or trace_payload.get("results") or []
                self.assertTrue(candidates, trace_payload)

    def test_context_index_build_subcommand_matches_default_behavior(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.context_index._timestamp_to_string",
            side_effect=self.fixed_timestamp,
        ):
            (cwd / ".agent" / "context").mkdir(parents=True)
            (cwd / "AGENTS.md").write_text("hello", encoding="utf-8")
            with mock.patch(
                "skillsmith.commands.context_index.KEY_PROJECT_FILES",
                ["AGENTS.md"],
            ):
                default_result = self.runner.invoke(main, ["context-index"])
                default_payload = json.loads((cwd / ".agent" / "context" / "index.json").read_text(encoding="utf-8"))
                build_result = self.runner.invoke(main, ["context-index", "build"])
                build_payload = json.loads((cwd / ".agent" / "context" / "index.json").read_text(encoding="utf-8"))

        self.assertEqual(default_result.exit_code, 0, default_result.output)
        self.assertEqual(build_result.exit_code, 0, build_result.output)
        self.assertEqual(default_payload["file_count"], build_payload["file_count"])
        self.assertEqual(default_payload["files"][0]["path"], build_payload["files"][0]["path"])
        self.assertIn("Context Index", build_result.output)
        self.assertIn(".agent/context/index.json", build_result.output)

    def test_context_index_query_preserves_legacy_ranking_with_optional_metadata_and_budgeted_tiers(self):
        with self.project_dir() as cwd:
            self.write_index_payload(
                cwd,
                [
                    {
                        "path": "docs/guide.md",
                        "freshness_score": 95,
                        "path_priority_score": 100,
                        "compressed_snippet": "project profile retrieval alpha beta",
                        "tier_snippets": {
                            "l0": "project profile retrieval alpha beta",
                            "l1": "project profile retrieval alpha beta with more context",
                            "l2": "project profile retrieval alpha beta with more context and detail",
                        },
                        "path_group": {"name": "docs", "type": "longform"},
                        "compaction": {
                            "strategy": "summary",
                            "source_paths": ["docs/guide.md", "docs/reference.md"],
                        },
                    },
                    {
                        "path": "docs/reference.md",
                        "freshness_score": 80,
                        "path_priority_score": 92,
                        "compressed_snippet": "project profile retrieval beta gamma",
                    },
                ],
            )

            l0_results = retrieve_context_candidates(cwd, "project profile", limit=2, tier="l0")
            l2_results = retrieve_context_candidates(cwd, "project profile", limit=2, tier="l2")
            result = self.runner.invoke(main, ["context-index", "query", "project profile", "--limit", "2", "--tier", "l2"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual([item["path"] for item in l0_results], ["docs/guide.md", "docs/reference.md"])
        self.assertEqual([item["path"] for item in l2_results], ["docs/guide.md", "docs/reference.md"])
        self.assertEqual(l0_results[0]["retrieval_tier"], "l0")
        self.assertEqual(l2_results[0]["retrieval_tier"], "l2")
        self.assertLess(len(l0_results[0]["selected_snippet"]), len(l2_results[0]["selected_snippet"]))
        path_group = l2_results[0].get("path_group")
        if isinstance(path_group, dict):
            self.assertEqual(path_group.get("name"), "docs")
        else:
            self.assertEqual(path_group, "docs")
        compaction = l2_results[0].get("compaction", l2_results[0].get("compaction_hint", {}))
        self.assertEqual(compaction.get("strategy", compaction.get("compaction_mode")), "summary" if "strategy" in compaction else "compact")
        self.assertIn("Tier: l2", result.output)
        self.assertIn("path=docs/guide.md", result.output)
        self.assertIn("path=docs/reference.md", result.output)

    def test_context_index_query_weights_override_changes_ranking(self):
        with self.project_dir() as cwd:
            self.write_index_payload(
                cwd,
                [
                    {
                        "path": "docs/strategy.md",
                        "freshness_score": 100,
                        "path_priority_score": 100,
                        "compressed_snippet": "alpha only",
                    },
                    {
                        "path": "docs/reference.md",
                        "freshness_score": 10,
                        "path_priority_score": 10,
                        "compressed_snippet": "alpha beta",
                    },
                ],
            )

            default_result = self.runner.invoke(main, ["context-index", "query", "alpha beta", "--limit", "2"])
            override_result = self.runner.invoke(
                main,
                [
                    "context-index",
                    "query",
                    "alpha beta",
                    "--limit",
                    "2",
                    "--weights",
                    '{"freshness": 0.1, "path_priority": 0.1, "lexical": 4, "semantic": 0}',
                ],
            )

        self.assertEqual(default_result.exit_code, 0, default_result.output)
        self.assertEqual(override_result.exit_code, 0, override_result.output)
        self.assertIn("base=", default_result.output)
        self.assertIn("final=", default_result.output)
        self.assertLess(default_result.output.index("path=docs/strategy.md"), default_result.output.index("path=docs/reference.md"))
        self.assertLess(override_result.output.index("path=docs/reference.md"), override_result.output.index("path=docs/strategy.md"))

    def test_context_index_query_reranks_top_candidates(self):
        with self.project_dir() as cwd:
            self.write_index_payload(
                cwd,
                [
                    {
                        "path": "alpha.md",
                        "freshness_score": 100,
                        "path_priority_score": 100,
                        "compressed_snippet": "zzz qqq",
                    },
                    {
                        "path": "beta.md",
                        "freshness_score": 100,
                        "path_priority_score": 100,
                        "compressed_snippet": "alpha beta",
                    },
                ],
            )
            self.write_query_policy(
                cwd,
                {
                    "weights": {
                        "freshness": 1,
                        "path_priority": 1,
                        "lexical": 0,
                        "semantic": 0,
                    },
                    "semantic": {
                        "enabled": True,
                        "dimensions": 12,
                    },
                    "rerank": {
                        "enabled": True,
                        "window": 2,
                        "weights": {
                            "freshness": 0,
                            "path_priority": 0,
                            "lexical": 0,
                            "semantic": 2,
                        },
                    },
                },
            )

            result = self.runner.invoke(main, ["context-index", "query", "alpha beta", "--limit", "2"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("rerank=", result.output)
        self.assertIn("Rerank window:", result.output)
        self.assertLess(result.output.index("path=beta.md"), result.output.index("path=alpha.md"))

    def test_context_index_skips_missing_files(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.context_index._timestamp_to_string",
            side_effect=self.fixed_timestamp,
        ):
            (cwd / ".agent" / "context").mkdir(parents=True)
            (cwd / "AGENTS.md").write_text("hello world", encoding="utf-8")

            with mock.patch(
                "skillsmith.commands.context_index.KEY_PROJECT_FILES",
                ["AGENTS.md", "README.md"],
            ):
                result = self.runner.invoke(main, ["context-index"])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads((cwd / ".agent" / "context" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["file_count"], 1)
            self.assertEqual([item["path"] for item in payload["files"]], ["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
