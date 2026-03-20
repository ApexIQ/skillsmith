import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.cli import main


def _write_skill(skill_dir: Path, *, name: str, description: str, tags: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        "version: 1.0.0\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"tags: [{tags}]\n"
        "---\n"
        "# Instructions\n"
        "Role instructions.\n",
        encoding="utf-8",
    )


class RolesCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_roles_project_json_supports_tag_and_search_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            _write_skill(
                cwd / ".agent" / "skills" / "researcher",
                name="researcher",
                description="Investigate requirements and constraints.",
                tags="agents, research",
            )
            _write_skill(
                cwd / ".agent" / "skills" / "reviewer",
                name="reviewer",
                description="Review changes and detect regressions.",
                tags="agents, quality",
            )
            previous_cwd = Path.cwd()
            try:
                os.chdir(cwd)
                result = self.runner.invoke(
                    main,
                    ["roles", "--source", "project", "--tag", "agents", "--search", "review", "--json"],
                )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(result.exit_code, 0, msg=result.output)
            payload = json.loads(result.output)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["source"], "project")
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["roles"][0]["name"], "reviewer")
            self.assertEqual(payload["roles"][0]["source"], "project")

    def test_roles_catalog_json_uses_catalog_entries(self) -> None:
        catalog = [
            {
                "name": "planner",
                "description": "Turn a goal into ordered implementation tasks.",
                "version": "2.0.0",
                "tags": ["planning", "agents"],
            }
        ]
        with mock.patch("skillsmith.commands.roles.load_catalog", return_value=catalog):
            result = self.runner.invoke(main, ["roles", "--source", "catalog", "--json"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["roles"][0]["name"], "planner")
        self.assertEqual(payload["roles"][0]["source"], "catalog")


if __name__ == "__main__":
    unittest.main()
