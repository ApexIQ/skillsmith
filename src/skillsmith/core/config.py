"""Configuration management for Skillsmith."""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from .exceptions import ConfigurationError

class SkillsmithConfig:
    """Central configuration management for Skillsmith projects."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize configuration.

        Args:
            project_root: Root directory of the project. Defaults to current directory.
        """
        self.root = project_root or Path.cwd()
        self.agent_dir = self.root / ".agent"
        self._profile: Optional[Dict[str, Any]] = None
        self._state: Optional[Dict[str, Any]] = None

    @property
    def is_initialized(self) -> bool:
        """Check if project is initialized.

        Returns:
            True if project is initialized, False otherwise.
        """
        return (self.agent_dir / "project_profile.yaml").exists()

    @property
    def profile(self) -> Dict[str, Any]:
        """Get project profile.

        Returns:
            Project profile dictionary.

        Raises:
            ConfigurationError: If profile cannot be loaded.
        """
        if self._profile is None:
            self._profile = self.load_profile()
        return self._profile

    @property
    def state(self) -> Dict[str, Any]:
        """Get project state.

        Returns:
            Project state dictionary.
        """
        if self._state is None:
            self._state = self.load_state()
        return self._state

    def load_profile(self) -> Dict[str, Any]:
        """Load project profile from disk.

        Returns:
            Project profile dictionary.

        Raises:
            ConfigurationError: If profile cannot be loaded.
        """
        profile_path = self.agent_dir / "project_profile.yaml"
        if not profile_path.exists():
            raise ConfigurationError(
                f"Project profile not found at {profile_path}. "
                "Run 'skillsmith init' to create one."
            )

        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to load project profile: {e}")

    def save_profile(self, profile: Dict[str, Any]) -> None:
        """Save project profile to disk.

        Args:
            profile: Profile dictionary to save.

        Raises:
            ConfigurationError: If profile cannot be saved.
        """
        profile_path = self.agent_dir / "project_profile.yaml"
        self.agent_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                yaml.dump(profile, f, sort_keys=False)
            self._profile = profile
        except Exception as e:
            raise ConfigurationError(f"Failed to save project profile: {e}")

    def load_state(self) -> Dict[str, Any]:
        """Load project state from STATE.md.

        Returns:
            Project state dictionary.
        """
        state_path = self.agent_dir / "STATE.md"
        if not state_path.exists():
            return {}

        # Parse STATE.md for key information
        state = {
            "last_updated": None,
            "current_objective": None,
            "recent_changes": [],
            "known_issues": []
        }

        try:
            content = state_path.read_text(encoding='utf-8')
            # Simple parsing - can be enhanced
            for line in content.split('\n'):
                if line.startswith('**Last Updated:**'):
                    state['last_updated'] = line.replace('**Last Updated:**', '').strip()
                elif line.startswith('## Current Objective'):
                    # Get next line as objective
                    pass
        except Exception:
            pass

        return state

    def get_skill_sources(self) -> List[str]:
        """Get configured skill sources.

        Returns:
            List of skill source paths/URLs.
        """
        return self.profile.get('trusted_skill_sources', ['local'])

    def get_priorities(self) -> List[str]:
        """Get project priorities.

        Returns:
            List of priority names.
        """
        return self.profile.get('priorities', [])

    def get_frameworks(self) -> List[str]:
        """Get project frameworks.

        Returns:
            List of framework names.
        """
        return self.profile.get('frameworks', [])

    def get_languages(self) -> List[str]:
        """Get project languages.

        Returns:
            List of language names.
        """
        languages = self.profile.get('languages', [])
        if isinstance(languages, str):
            return [languages]
        return languages

    def get_app_type(self) -> str:
        """Get application type.

        Returns:
            Application type string.
        """
        return self.profile.get('app_type', 'library')

    def get_trust_score(self) -> int:
        """Get minimum trust score requirement.

        Returns:
            Minimum trust score.
        """
        return self.profile.get('minimum_remote_trust', 65)

    def is_remote_allowed(self, domain: str) -> bool:
        """Check if remote domain is allowed.

        Args:
            domain: Domain to check.

        Returns:
            True if domain is allowed, False otherwise.
        """
        allowed_domains = self.profile.get('allowed_remote_domains', [])
        return domain in allowed_domains