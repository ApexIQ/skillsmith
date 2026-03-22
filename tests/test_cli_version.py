import os
import unittest
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

import skillsmith
from skillsmith.cli import main


class CliVersionTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_root_version_flag_prints_package_version(self):
        result = self.runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(skillsmith.__version__, result.output)


if __name__ == "__main__":
    unittest.main()
