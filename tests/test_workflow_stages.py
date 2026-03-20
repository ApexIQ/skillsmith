from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmith.commands.workflow_engine import WORKFLOW_STAGE_ORDER, build_workflow


class WorkflowStageTests(unittest.TestCase):
    def _project_dir(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        cwd = Path(temp_dir.name)
        (cwd / ".agent" / "context").mkdir(parents=True, exist_ok=True)
        (cwd / ".agent" / "project_profile.yaml").write_text(
            "\n".join(
                [
                    "idea: Stage workflow demo",
                    "project_stage: greenfield",
                    "app_type: application",
                    "frameworks:",
                    "  - python",
                    "priorities:",
                    "  - reliability",
                    "  - testing",
                ]
            ),
            encoding="utf-8",
        )
        (cwd / ".agent" / "context" / "project-context.md").write_text(
            "# Project Context\nStage workflow demo.\n",
            encoding="utf-8",
        )
        return temp_dir, cwd

    def test_build_workflow_emits_stage_structure_and_legacy_steps(self):
        temp_dir, cwd = self._project_dir()
        self.addCleanup(temp_dir.cleanup)

        catalog = [
            {
                "name": "implementation",
                "description": "implement features and verify changes",
                "tags": ["feature", "implementation"],
                "version": "1.0.0",
            }
        ]
        with mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            previous_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                workflow = build_workflow("implement a feature", cwd, max_skills=3)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual([stage["name"] for stage in workflow["stages"]], list(WORKFLOW_STAGE_ORDER))
        for stage in workflow["stages"]:
            self.assertTrue(stage["objectives"], stage)
            self.assertTrue(stage["acceptance_checks"], stage)
            self.assertTrue(stage["evidence"], stage)
            self.assertNotIn("placeholder", " ".join(stage["acceptance_checks"]).lower())
            self.assertNotIn("placeholder", " ".join(stage["objectives"]).lower())

        self.assertIsInstance(workflow["steps"], list)
        self.assertGreaterEqual(len(workflow["steps"]), len(WORKFLOW_STAGE_ORDER))
        self.assertIn("Read .agent/project_profile.yaml", workflow["steps"][0])
        self.assertTrue(any(step.startswith("Discover stage:") for step in workflow["steps"]))

    def test_build_workflow_tailors_stage_content_to_goal_kind(self):
        temp_dir, cwd = self._project_dir()
        self.addCleanup(temp_dir.cleanup)

        catalog = [
            {
                "name": "debugging",
                "description": "debug and fix bugs",
                "tags": ["debug", "bugfix"],
                "version": "1.0.0",
            }
        ]
        with mock.patch("skillsmith.commands.workflow_engine.load_catalog", return_value=catalog):
            previous_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                debug_workflow = build_workflow("debug login bug", cwd, max_skills=3)
                deploy_workflow = build_workflow("deploy release", cwd, max_skills=3)
            finally:
                os.chdir(previous_cwd)

        debug_build = next(stage for stage in debug_workflow["stages"] if stage["name"] == "build")
        self.assertIn("Reproduce the issue and capture the failing behavior.", debug_build["objectives"])
        self.assertIn("Implement the fix with focused verification for the affected area.", debug_build["objectives"])
        self.assertTrue(any("Reproduce the issue" in step for step in debug_workflow["steps"]))
        self.assertTrue(any("Implement the fix" in step for step in debug_workflow["steps"]))

        ship_stage = next(stage for stage in deploy_workflow["stages"] if stage["name"] == "ship")
        self.assertIn("Check release readiness against the current project stage, priorities, and target tools.", ship_stage["objectives"])
        self.assertTrue(any("rollback notes" in objective.lower() for objective in ship_stage["objectives"]))
        self.assertTrue(any("rollback notes" in step.lower() for step in deploy_workflow["steps"]))


if __name__ == "__main__":
    unittest.main()
