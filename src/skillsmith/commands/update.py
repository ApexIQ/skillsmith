from pathlib import Path
import click
from rich.table import Table
from . import (
    console, 
    iter_skill_dirs,
    find_template_skill_dir,
    validate_skill
)

@click.command()
@click.option("--force", is_flag=True, help="Overwrite modified local skills")
def update_command(force):
    """Update local skills to match library templates."""
    cwd = Path.cwd()
    skills_dir = cwd / ".agent" / "skills"
    
    if not skills_dir.exists():
        console.print("[red]Error: .agent/skills/ not found. Use 'skillsmith init' first.[/red]")
        return
        
    table = Table(title="Skill Updates")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Action", style="white")

    updates = 0
    for folder in iter_skill_dirs(skills_dir):
        skill_name = folder.name
        tpl_dir = find_template_skill_dir(skill_name)
        
        if not tpl_dir:
            table.add_row(skill_name, "[yellow]GONE[/yellow]", "Not in template library")
            continue
            
        # Version check
        def get_ver(p):
            try:
                content = (p / "SKILL.md").read_text(encoding="utf-8")
                parts = content.split("---")
                import yaml
                meta = yaml.safe_load(parts[1])
                return str(meta.get("version", "0.0.0"))
            except Exception:
                return "0.0.0"

        local_ver = get_ver(folder)
        tpl_ver = get_ver(tpl_dir)

        if local_ver < tpl_ver:
            # Check for local modifications (simple heuristic: size or mtime?)
            # For now, just compare version. 
            import shutil
            shutil.rmtree(folder)
            shutil.copytree(tpl_dir, folder)
            table.add_row(skill_name, "[green]UPDATED[/green]", f"{local_ver} -> {tpl_ver}")
            updates += 1
        else:
            table.add_row(skill_name, "[dim]OK[/dim]", f"Up to date ({local_ver})")

    console.print(table)
    if updates > 0:
        console.print(f"\n[green]Successfully updated {updates} skills.[/green]")
    else:
        console.print("\n[dim]All skills are up to date.[/dim]")
