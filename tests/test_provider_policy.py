import unittest

from skillsmith.commands.providers import SkillCandidate, candidate_allowed, install_policy_for_profile


class ProviderPolicyTests(unittest.TestCase):
    def test_install_policy_includes_new_profile_driven_gates(self):
        policy = install_policy_for_profile(
            {
                "allow_remote_skills": True,
                "trusted_skill_sources": ["Local", "skills.sh"],
                "blocked_skill_sources": ["github", "gitlab"],
                "min_remote_trust_score": 72,
                "min_remote_freshness_score": 8,
                "required_remote_licenses": ["MIT", "Apache-2.0"],
            }
        )

        self.assertEqual(policy["allowed_sources"], {"local", "skills.sh"})
        self.assertEqual(policy["blocked_skill_sources"], {"github", "gitlab"})
        self.assertEqual(policy["min_remote_trust_score"], 72)
        self.assertEqual(policy["min_remote_freshness_score"], 8)
        self.assertEqual(policy["required_remote_licenses"], {"mit", "apache2.0"})

    def test_allow_remote_default_includes_builtin_provider_sources(self):
        policy = install_policy_for_profile({"allow_remote_skills": True})

        self.assertTrue(
            {"local", "skills.sh", "huggingface", "github-topics", "org-registry"}.issubset(policy["allowed_sources"])
        )

    def test_local_candidates_bypass_remote_policy_gates(self):
        profile = {
            "allow_remote_skills": False,
            "trusted_skill_sources": ["skills.sh"],
            "blocked_skill_sources": ["skills.sh"],
            "min_remote_trust_score": 99,
            "min_remote_freshness_score": 99,
            "required_remote_licenses": ["MIT"],
        }
        candidate = SkillCandidate(
            name="local-skill",
            description="Local skill",
            source="local",
            trust_score=1,
            freshness_score=0,
            metadata={"license": "GPL-3.0"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_remote_candidate_is_allowed_when_all_gates_pass(self):
        profile = {
            "allow_remote_skills": True,
            "trusted_skill_sources": ["skills.sh"],
            "blocked_skill_sources": ["github"],
            "min_remote_trust_score": 70,
            "min_remote_freshness_score": 8,
            "required_remote_licenses": ["MIT"],
        }
        candidate = SkillCandidate(
            name="remote-skill",
            description="Remote skill",
            source="skills.sh",
            trust_score=80,
            freshness_score=11,
            metadata={"license": "MIT"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_org_registry_candidate_bypasses_remote_gate(self):
        profile = {
            "allow_remote_skills": False,
            "trusted_skill_sources": ["skills.sh"],
            "blocked_skill_sources": ["skills.sh"],
            "min_remote_trust_score": 99,
            "min_remote_freshness_score": 99,
            "required_remote_licenses": ["MIT"],
        }
        candidate = SkillCandidate(
            name="registry-skill",
            description="Org registry skill",
            source="org-registry",
            trust_score=1,
            freshness_score=0,
            metadata={"license": "GPL-3.0"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_blocked_remote_source_returns_clear_message(self):
        profile = {
            "allow_remote_skills": True,
            "trusted_skill_sources": ["skills.sh"],
            "blocked_skill_sources": ["skills.sh"],
            "min_remote_trust_score": 70,
            "min_remote_freshness_score": 8,
            "required_remote_licenses": ["MIT"],
        }
        candidate = SkillCandidate(
            name="blocked-skill",
            description="Blocked skill",
            source="skills.sh",
            trust_score=80,
            freshness_score=11,
            metadata={"license": "MIT"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "source 'skills.sh' is blocked by blocked_skill_sources")

    def test_remote_candidate_fails_freshness_gate_with_clear_message(self):
        profile = {
            "allow_remote_skills": True,
            "trusted_skill_sources": ["skills.sh"],
            "min_remote_trust_score": 70,
            "min_remote_freshness_score": 8,
            "required_remote_licenses": ["MIT"],
        }
        candidate = SkillCandidate(
            name="stale-skill",
            description="Stale skill",
            source="skills.sh",
            trust_score=80,
            freshness_score=4,
            metadata={"license": "MIT"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "freshness score 4 is below min_remote_freshness_score 8")

    def test_remote_candidate_fails_required_license_gate_with_clear_message(self):
        profile = {
            "allow_remote_skills": True,
            "trusted_skill_sources": ["skills.sh"],
            "min_remote_trust_score": 70,
            "min_remote_freshness_score": 8,
            "required_remote_licenses": ["MIT", "Apache-2.0"],
        }
        candidate = SkillCandidate(
            name="unlicensed-skill",
            description="Unlicensed skill",
            source="skills.sh",
            trust_score=80,
            freshness_score=11,
            metadata={"license": "GPL-3.0"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "license 'GPL-3.0' is not in required_remote_licenses [MIT, Apache-2.0]")

    def test_existing_trusted_skill_sources_allowlist_is_still_honored(self):
        profile = {
            "allow_remote_skills": True,
            "trusted_skill_sources": ["github"],
        }
        candidate = SkillCandidate(
            name="skills-sh-skill",
            description="Remote skill",
            source="skills.sh",
            trust_score=90,
            freshness_score=12,
            metadata={"license": "MIT"},
        )

        allowed, reason = candidate_allowed(candidate, profile)

        self.assertFalse(allowed)
        self.assertEqual(reason, "source 'skills.sh' is not in trusted_skill_sources")
