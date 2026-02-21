import yaml
from pathlib import Path
import click
from rich.table import Table
from . import (
    console, 
    iter_skill_dirs,
    validate_skill,
    validate_skill_agentskills
)

@click.command()
@click.option("--local", is_flag=True, help="Lint local .agent/skills (default)")
@click.option("--spec", "spec", default="agentskills", help="Specification to lint against (default: agentskills)")
def lint_command(local, spec):
    """Validate skill structures and metadata"""
    cwd = Path.cwd()
    skills_dir = cwd / ".agent" / "skills"
    
    if not skills_dir.exists():
        console.print("[red]Error: .agent/skills/ not found.[/red]")
        return
        
    table = Table(title=f"Skill Linter (Spec: {spec})")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Messages", style="white")

    found = False
    for folder in iter_skill_dirs(skills_dir):
        found = True
        if spec == "agentskills":
            is_valid, messages = validate_skill_agentskills(folder)
        else:
            is_valid, msg = validate_skill(folder)
            messages = [msg]

        status = "[green]PASS[/green]" if is_valid else "[red]FAIL[/red]"
        table.add_row(folder.name, status, ", ".join(messages))

    if not found:
        console.print("[yellow]No skills found to lint.[/yellow]")
    else:
        console.print(table)
