import click
from rich.table import Table
from . import console

@click.command(name="commands")
@click.option("--all", is_flag=True, help="List all CLI and agentic slash commands")
def commands_command(all: bool):
    """List every command available in the Skillsmith universe (77+)."""
    
    table = Table(title="Skillsmith Command Registry", title_style="bold magenta")
    table.add_column("Type", justify="center", style="cyan")
    table.add_column("Command", style="bold green")
    table.add_column("Operational Focus", style="dim")

    # CLI Section
    table.add_section()
    table.add_row("CLI", "skillsmith init", "Induction & Profile Inference")
    table.add_row("CLI", "skillsmith sync", "Architectural Alignment")
    table.add_row("CLI", "skillsmith understand", "CK Intelligence Bridge")
    table.add_row("CLI", "skillsmith ready", "Readiness Quality Gate")
    table.add_row("CLI", "skillsmith add", "Subagent Acquisition")
    table.add_row("CLI", "skillsmith swarm", "Multi-Agent Mission Control")
    table.add_row("CLI", "skillsmith evolve", "Self-Healing Evolution")
    table.add_row("CLI", "skillsmith metrics", "Performance Analytics")
    table.add_row("CLI", "skillsmith tree", "Thinking Tree Visualization")
    table.add_row("CLI", "skillsmith start", "Bootstrap-to-Readiness Flow")

    # Slash Section (Categorized)
    table.add_section()
    # Feature
    table.add_row("SLASH", "/plan-feature", "Automated Technical Design")
    table.add_row("SLASH", "/implement-feature", "Code & Test Synthesis")
    table.add_row("SLASH", "/test", "Full Test Suite Generation")
    # Intelligence
    table.add_row("SLASH", "/explain", "Detailed Code Walkthrough")
    table.add_row("SLASH", "/context", "Task-Specific File Retrieval")
    table.add_row("SLASH", "/search", "Global Ecosystem Discovery")
    # Quality
    table.add_row("SLASH", "/review-changes", "Pre-Commit Peer Review")
    table.add_row("SLASH", "/security", "OWASP Security Audit")
    table.add_row("SLASH", "/performance", "Latency & Resource Profile")
    table.add_row("SLASH", "/doc", "Markdown Documentation Sync")
    # Debug
    table.add_row("SLASH", "/debug", "Root-Cause Investigation")
    table.add_row("SLASH", "/fix", "Targeted Bug/Lint Repair")
    table.add_row("SLASH", "/verify", "Mission Success Validation")
    # Advance
    table.add_row("SLASH", "/autonomous", "Bounded Execution Loop")
    table.add_row("SLASH", "/migrate", "Technological Modernization")
    
    console.print(table)
    console.print("\n[dim]Note: Slash commands (/) are executed inside your AI tool (Claude, Cursor, etc.).[/dim]")
    console.print("[dim]Run `skillsmith cookbook` to see recipes for these commands.[/dim]")
