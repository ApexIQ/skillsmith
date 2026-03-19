import json
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


def _skill_entries(count: int) -> list[dict]:
    entries = []
    for index in range(count):
        entries.append(
            {
                "name": f"skill-{index:02d}",
                "source": "local",
                "path": f".agent/skills/skill-{index:02d}",
                "checksum": "",
                "trust_score": 90,
                "recommendation": {"reasons": ["manual install"]},
            }
        )
    return entries


class LockfileReportingCoverageTests(unittest.TestCase):
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

    def test_report_lists_beyond_ten_lockfile_entries(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            (cwd / "skills.lock.json").write_text(
                json.dumps({"version": 1, "skills": _skill_entries(12)}),
                encoding="utf-8",
            )

            result = self.runner.invoke(main, ["report"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("skill-11", result.output)
            self.assertNotIn("Showing 10 of", result.output)

    def test_audit_json_includes_all_lockfile_entries(self):
        with self.project_dir() as cwd:
            init_result = self.runner.invoke(main, ["init", "--minimal"])
            self.assertEqual(init_result.exit_code, 0, init_result.output)
            (cwd / "skills.lock.json").write_text(
                json.dumps({"version": 1, "skills": _skill_entries(12)}),
                encoding="utf-8",
            )

            result = self.runner.invoke(main, ["audit", "--json"])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            lockfile_checks = [item for item in payload["checks"] if item["section"] == "lockfile"]
            self.assertEqual(len(lockfile_checks), 12)


if __name__ == "__main__":
    unittest.main()
