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


class QuickstartSmokeTests(unittest.TestCase):
    def test_readme_quickstart_sequence(self):
        runner = CliRunner()
        work_root = ROOT / ".test-smoke"
        work_root.mkdir(parents=True, exist_ok=True)
        project = work_root / f"quickstart-{int(time.time() * 1000)}"
        project.mkdir(parents=True, exist_ok=False)

        previous = Path.cwd()
        try:
            os.chdir(project)
            guided_input = "\n" * 40
            init_result = runner.invoke(main, ["init", "--guided"], input=guided_input)
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            doctor_result = runner.invoke(main, ["doctor"])
            self.assertEqual(doctor_result.exit_code, 0, doctor_result.output)

            compose_result = runner.invoke(main, ["compose", "build a project summary"])
            self.assertEqual(compose_result.exit_code, 0, compose_result.output)
            self.assertIn("Generated Workflow", compose_result.output)
        finally:
            os.chdir(previous)
            shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
