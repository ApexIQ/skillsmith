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


class StabilityContractTests(unittest.TestCase):
    def test_readme_mentions_all_cli_top_level_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        commands = set(main.commands.keys())
        missing = sorted(command for command in commands if f"skillsmith {command}" not in readme)
        self.assertEqual(missing, [], f"README is missing command docs for: {', '.join(missing)}")

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
