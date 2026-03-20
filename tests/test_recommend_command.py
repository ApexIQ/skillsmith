from __future__ import annotations

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
from skillsmith.commands.providers import SkillCandidate


class RecommendCommandTests(unittest.TestCase):
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

    def _candidate(self) -> SkillCandidate:
        return SkillCandidate(
            name="python_packaging",
            description="Package and publish Python libraries",
            source="local",
            trust_score=95,
            install_ref="python_packaging",
            metadata={"starter_pack": True, "starter_pack_label": "library:pytest"},
        )

    def _explanation(self) -> dict:
        return {
            "reasons": ["starter pack:library:pytest", "query:python"],
            "matched_query": ["python"],
            "matched_profile": ["pytest"],
            "source_bonus": 15,
            "profile_bonus": 45,
            "metadata_bonus": 3,
            "freshness_source": "updated_at",
            "license": "MIT",
            "maintainer": "skillsmith",
        }

    def test_recommend_default_output_still_renders_table(self):
        with self.project_dir(), mock.patch(
            "skillsmith.commands.recommend.explain_recommendations_for_profile",
            return_value=[(self._candidate(), self._explanation())],
        ):
            result = self.runner.invoke(main, ["recommend"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Recommended Skills", result.output)
        self.assertIn("python_pa", result.output)
        self.assertIn("Package", result.output)
        self.assertIn("starter", result.output)

    def test_recommend_json_emits_machine_readable_payload(self):
        with self.project_dir(), mock.patch(
            "skillsmith.commands.recommend.explain_recommendations_for_profile",
            return_value=[(self._candidate(), self._explanation())],
        ):
            result = self.runner.invoke(main, ["recommend", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("profile_source", payload)
        self.assertIn("recommendations", payload)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["limit"], 5)
        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["name"], "python_packaging")
        self.assertEqual(recommendation["eligibility"]["passed"], True)
        self.assertEqual(recommendation["explanation"]["matched_query"], ["python"])
        self.assertEqual(recommendation["explanation"]["license"], "MIT")

    def test_recommend_explain_surfaces_gate_failure_reason(self):
        candidate = SkillCandidate(
            name="remote_skill",
            description="Remote skill",
            source="skills.sh",
            trust_score=40,
            install_ref="remote/skill",
            metadata={},
        )
        with self.project_dir(), mock.patch(
            "skillsmith.commands.recommend.explain_recommendations_for_profile",
            return_value=[(candidate, self._explanation())],
        ), mock.patch(
            "skillsmith.commands.recommend.candidate_allowed",
            return_value=(False, "source 'skills.sh' is not in trusted_skill_sources"),
        ):
            result = self.runner.invoke(main, ["recommend", "--explain"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gate", result.output)
        self.assertIn("failed: source 'skills.sh' is not in trusted_skill_sources", result.output)
        self.assertIn("matched_query=python", result.output)


if __name__ == "__main__":
    unittest.main()
