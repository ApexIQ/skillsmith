from pathlib import Path
import click
from . import (
    console, 
    iter_skill_dirs
)

@click.command()
def budget_command():
    """Analyze context token budget across all platform files and skills."""
    cwd = Path.cwd()
    
    def estimate_tokens(text: str):
        """Rough token estimate: ~4 chars per token (GPT/Claude standard)."""
        return len(text) // 4

    total_tokens = 0
    # Core platform files
    platform_files = [
        "AGENTS.md", "GEMINI.md", "CLAUDE.md", ".cursorrules", 
        ".windsurfrules", ".github/copilot-instructions.md"
    ]
    
    console.print("[bold cyan]Context Budget Analysis[/bold cyan]\n")
    
    for fname in platform_files:
        path = cwd / fname
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            tokens = estimate_tokens(content)
            total_tokens += tokens
            console.print(f"  [green]{tokens:>6}[/green] tokens - {fname}")

    # .agent state files
    state_files = [".agent/PROJECT.md", ".agent/ROADMAP.md", ".agent/STATE.md"]
    for fname in state_files:
        path = cwd / fname
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            tokens = estimate_tokens(content)
            total_tokens += tokens
            console.print(f"  [green]{tokens:>6}[/green] tokens - {fname}")

    # Skills
    skills_dir = cwd / ".agent" / "skills"
    if skills_dir.exists():
        skill_tokens = 0
        for folder in iter_skill_dirs(skills_dir):
            for f in folder.glob("**/*"):
                if f.is_file() and f.suffix in [".md", ".py", ".sh", ".json"]:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    skill_tokens += estimate_tokens(content)
        total_tokens += skill_tokens
        console.print(f"  [green]{skill_tokens:>6}[/green] tokens - .agent/skills/ (total)")

    console.print("\n" + "─" * 40)
    console.print(f"  [bold]{total_tokens:>6}[/bold] TOTAL estimated context tokens")
    console.print("─" * 40)
    
    # Warnings based on standard context windows
    if total_tokens > 20000:
        console.print("[yellow]Warning: Large context. You may face higher latency or context truncation.[/yellow]")
    if total_tokens > 100000:
        console.print("[red]Critical: Context exceeds many model limits. Compaction recommended.[/red]")
