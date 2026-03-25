"""Custom exceptions for Skillsmith."""

class SkillsmithError(Exception):
    """Base exception for all Skillsmith errors."""
    pass

class ConfigurationError(SkillsmithError):
    """Raised when there's a configuration issue."""
    pass

class ValidationError(SkillsmithError):
    """Raised when validation fails."""
    pass

class SkillNotFoundError(SkillsmithError):
    """Raised when a skill cannot be found."""
    pass

class ProjectNotInitializedError(SkillsmithError):
    """Raised when attempting operations on an uninitialized project."""
    pass

class TrustVerificationError(SkillsmithError):
    """Raised when trust verification fails."""
    pass

class MemoryError(SkillsmithError):
    """Raised when there's an issue with the memory system."""
    pass

class SwarmExecutionError(SkillsmithError):
    """Raised when swarm execution fails."""
    pass

class CommandExecutionError(SkillsmithError):
    """Raised when a command fails to execute."""
    pass