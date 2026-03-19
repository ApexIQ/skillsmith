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


class DoctorBehaviorTests(unittest.TestCase):
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

    def test_doctor_exits_non_zero_when_profile_yaml_is_invalid(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)

            profile_path = cwd / ".agent" / "project_profile.yaml"
            profile_path.write_text("idea: broken: yaml: [", encoding="utf-8")

            result = self.runner.invoke(main, ["doctor"])

            self.assertNotEqual(result.exit_code, 0, result.output)
            self.assertIn("Failed to load project profile", result.output)


if __name__ == "__main__":
    unittest.main()
