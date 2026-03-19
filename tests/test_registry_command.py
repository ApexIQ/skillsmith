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


class RegistryCommandTests(unittest.TestCase):
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

    def test_registry_add_approval_history_and_filters(self):
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.registry._timestamp_to_string",
            return_value="2026-03-19T12:00:00Z",
        ):
            add_alpha = self.runner.invoke(
                main,
                [
                    "registry",
                    "add",
                    "alpha-skill",
                    "--state",
                    "draft",
                    "--description",
                    "Alpha registry entry",
                    "--source",
                    "local",
                    "--owner",
                    "team-a",
                    "--owner",
                    "team-c",
                    "--tag",
                    "platform",
                    "--notes",
                    "initial draft",
                ],
            )
            add_beta = self.runner.invoke(
                main,
                [
                    "registry",
                    "add",
                    "beta-skill",
                    "--state",
                    "approved",
                    "--description",
                    "Beta registry entry",
                    "--source",
                    "github",
                    "--owner",
                    "team-b",
                    "--tag",
                    "platform",
                ],
            )
            request_alpha = self.runner.invoke(
                main,
                [
                    "registry",
                    "request-approval",
                    "alpha-skill",
                    "--by",
                    "reviewer-a",
                    "--note",
                    "ready for review",
                ],
            )
            approve_alpha = self.runner.invoke(
                main,
                [
                    "registry",
                    "approve",
                    "alpha-skill",
                    "--by",
                    "reviewer-a",
                    "--note",
                    "looks good",
                ],
            )
            deprecate_alpha = self.runner.invoke(
                main,
                [
                    "registry",
                    "set-state",
                    "alpha-skill",
                    "deprecated",
                    "--by",
                    "reviewer-a",
                    "--note",
                    "retired",
                ],
            )

            self.assertEqual(add_alpha.exit_code, 0, add_alpha.output)
            self.assertEqual(add_beta.exit_code, 0, add_beta.output)
            self.assertEqual(request_alpha.exit_code, 0, request_alpha.output)
            self.assertEqual(approve_alpha.exit_code, 0, approve_alpha.output)
            self.assertEqual(deprecate_alpha.exit_code, 0, deprecate_alpha.output)

            payload = json.loads((cwd / ".agent" / "registry" / "skills.json").read_text(encoding="utf-8"))
            skills = {item["name"]: item for item in payload["skills"]}

            alpha = skills["alpha-skill"]
            beta = skills["beta-skill"]
            self.assertEqual(alpha["lifecycle_state"], "deprecated")
            self.assertEqual(alpha["approval_status"], "withdrawn")
            self.assertEqual(alpha["ownership"]["owners"], ["team-a", "team-c"])
            self.assertEqual(alpha["ownership"]["primary_owner"], "team-a")
            self.assertEqual(beta["ownership"]["owners"], ["team-b"])
            self.assertEqual(beta["approval_status"], "approved")
            self.assertEqual([event["action"] for event in alpha["change_history"]], ["create", "request-approval", "approve", "set-state"])
            self.assertEqual(alpha["approvals"][0]["actor"], "reviewer-a")
            self.assertIn("ready for review", alpha["change_history"][1]["note"])
            self.assertIn("looks good", alpha["change_history"][2]["note"])

            history_result = self.runner.invoke(main, ["registry", "history", "alpha-skill"])
            self.assertEqual(history_result.exit_code, 0, history_result.output)
            self.assertIn("Registry History", history_result.output)

            approved_result = self.runner.invoke(main, ["registry", "list", "--approval-state", "approved"])
            self.assertEqual(approved_result.exit_code, 0, approved_result.output)
            self.assertIn("Showing 1 matching registry entries", approved_result.output)
            self.assertIn("team-b", approved_result.output)
            self.assertNotIn("team-a", approved_result.output)

            filtered_result = self.runner.invoke(main, ["registry", "list", "--owner", "team-b"])
            self.assertEqual(filtered_result.exit_code, 0, filtered_result.output)
            self.assertIn("Showing 1 matching registry entries", filtered_result.output)
            self.assertIn("team-b", filtered_result.output)
            self.assertNotIn("team-a", filtered_result.output)

    def test_registry_list_handles_empty_registry(self):
        with self.project_dir():
            result = self.runner.invoke(main, ["registry", "list", "--state", "deprecated"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("No registry entries matched", result.output)


if __name__ == "__main__":
    unittest.main()
