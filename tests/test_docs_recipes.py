import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RECIPE_DIR = ROOT / "docs" / "recipes"
RECIPE_FILES = [
    RECIPE_DIR / "local-bootstrap.md",
    RECIPE_DIR / "ci-gate-flow.md",
    RECIPE_DIR / "team-onboarding.md",
]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FENCED_CODE_RE = re.compile(r"```(?:bash|sh)?\n(.*?)```", flags=re.DOTALL)


class DocsRecipeTests(unittest.TestCase):
    def test_recipe_files_exist(self):
        for recipe in RECIPE_FILES:
            with self.subTest(recipe=recipe.name):
                self.assertTrue(recipe.exists(), f"Missing recipe file: {recipe}")

    def test_readme_links_to_recipe_docs(self):
        content = README.read_text(encoding="utf-8", errors="ignore")
        links = {match.group(1) for match in LINK_RE.finditer(content)}
        for recipe in RECIPE_FILES:
            rel = recipe.relative_to(ROOT).as_posix()
            with self.subTest(link=rel):
                self.assertIn(rel, links, f"README is missing link to {rel}")

    def test_readme_and_recipes_skillsmith_commands_are_valid(self):
        import os
        import sys

        if str(ROOT / "src") not in sys.path:
            sys.path.insert(0, str(ROOT / "src"))
        from skillsmith.cli import main

        valid_commands = set(main.commands.keys())
        valid_commands.add("--help")
        docs = [README, *RECIPE_FILES]
        for doc in docs:
            content = doc.read_text(encoding="utf-8", errors="ignore")
            blocks = FENCED_CODE_RE.findall(content)
            for block in blocks:
                for raw_line in block.splitlines():
                    line = raw_line.strip()
                    if not line or not line.startswith("skillsmith "):
                        continue
                    tokens = line.split()
                    if len(tokens) < 2:
                        self.fail(f"Malformed command snippet in {doc}: {line}")
                    command = tokens[1]
                    if command.startswith("<") and command.endswith(">"):
                        continue
                    with self.subTest(doc=doc.name, command=command, line=line):
                        self.assertIn(command, valid_commands, f"Unknown skillsmith command in {doc}: {line}")


if __name__ == "__main__":
    unittest.main()
