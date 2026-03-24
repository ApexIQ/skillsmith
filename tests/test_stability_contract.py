import os
import shutil
import re
import time
import unittest
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

import skillsmith
from skillsmith.cli import main

STABLE_CLI_SECTION_RE = re.compile(r"### Stable Top-Level CLI Surface\n\n(.*?)(?:\n### |\n## |\Z)", re.DOTALL)
STABLE_CLI_COMMAND_RE = re.compile(r"^- `skillsmith ([^`]+)`$", re.MULTILINE)


class StabilityContractTests(unittest.TestCase):
    def test_readme_documents_core_and_advanced_command_tiers(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("### Core Daily Commands", readme)
        self.assertIn("### Advanced and Admin Commands", readme)

    def test_readme_stable_cli_surface_matches_top_level_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        match = STABLE_CLI_SECTION_RE.search(readme)
        self.assertIsNotNone(match, "README is missing the Stable Top-Level CLI Surface section")
        section = match.group(1)
        documented = {match.group(1) for match in STABLE_CLI_COMMAND_RE.finditer(section)}
        self.assertEqual(documented, set(main.commands.keys()))

    def test_readme_package_version_matches_project_version(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"Package version:\s*`([^`]+)`", readme)
        self.assertIsNotNone(match, "README is missing the package version callout")
        self.assertEqual(match.group(1), skillsmith.__version__)

    def test_readme_documents_readiness_workflow_and_artifact_dir(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("skillsmith ready", readme)
        self.assertIn("skillsmith report --artifact-dir", readme)

    def test_ci_recipe_documents_readiness_workflow_and_artifact_dir(self):
        recipe = (ROOT / "docs" / "recipes" / "ci-gate-flow.md").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("skillsmith ready", recipe)
        self.assertIn("skillsmith report --artifact-dir", recipe)
        self.assertIn("Recommended Automated Test Matrix", recipe)
        self.assertIn("tests.test_machine_output_contract", recipe)

    def test_compose_deprecated_planner_editor_option(self):
        runner = CliRunner()
        sandbox = ROOT / ".test-stability"
        sandbox.mkdir(parents=True, exist_ok=True)
        project = sandbox / f"contract-{int(time.time() * 1000)}"
        project.mkdir(parents=True, exist_ok=False)
        previous = Path.cwd()

        try:
            os.chdir(project)
            init_result = runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            compose_result = runner.invoke(main, ["compose", "build quick summary", "--planner-editor"])
            self.assertEqual(compose_result.exit_code, 0, compose_result.output)
            self.assertIn("--planner-editor is deprecated", compose_result.output)
        finally:
            os.chdir(previous)
            shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
