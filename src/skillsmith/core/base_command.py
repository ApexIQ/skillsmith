"""Base command class for all Skillsmith commands."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

class BaseCommand(ABC):
    """Base class for all Skillsmith commands."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize base command.

        Args:
            project_root: Root directory of the project. Defaults to current directory.
        """
        self.root = project_root or Path.cwd()
        self.console = Console()
        self.agent_dir = self.root / ".agent"

    def validate_project(self) -> bool:
        """Validate that we're in a Skillsmith project.

        Returns:
            True if valid project, False otherwise.
        """
        return self.agent_dir.exists() and (self.agent_dir / "project_profile.yaml").exists()

    def ensure_project(self) -> None:
        """Ensure we're in a valid project, raise if not."""
        if not self.validate_project():
            raise ValueError(
                "Not in a Skillsmith project. Run 'skillsmith init' first."
            )

    @abstractmethod
    def validate(self) -> bool:
        """Validate command prerequisites.

        Returns:
            True if validation passes, False otherwise.
        """
        pass

    @abstractmethod
    def execute(self, **kwargs) -> int:
        """Execute the command.

        Returns:
            Exit code (0 for success, non-zero for failure).
        """
        pass

    def print_success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def print_error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"[bold red]✗[/bold red] {message}")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")

    def print_info(self, message: str) -> None:
        """Print info message."""
        self.console.print(f"[bold blue]ℹ[/bold blue] {message}")