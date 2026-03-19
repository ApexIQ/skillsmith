import filecmp
import shutil
from pathlib import Path

import click
from rich.table import Table

from . import console, find_template_skill_dir, iter_skill_dirs


def _directories_match(left: Path, right: Path) -> bool:
    comparison = filecmp.dircmp(left, right)
    if comparison.left_only or comparison.right_only or comparison.diff_files or comparison.funny_files:
        return False
    return all(_directories_match(left / name, right / name) for name in comparison.common_dirs)


def _get_skill_version(skill_dir: Path) -> str:
    try:
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        parts = content.split("---")
        import yaml

        metadata = yaml.safe_load(parts[1])
        return str(metadata.get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


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
        template_dir = find_template_skill_dir(skill_name)

        if not template_dir:
            table.add_row(skill_name, "[yellow]GONE[/yellow]", "Not in template library")
            continue

        local_ver = _get_skill_version(folder)
        template_ver = _get_skill_version(template_dir)

        if local_ver < template_ver:
            if not force and not _directories_match(folder, template_dir):
                table.add_row(
                    skill_name,
                    "[yellow]SKIP[/yellow]",
                    f"Local changes detected ({local_ver} -> {template_ver}); use --force",
                )
                continue

            shutil.rmtree(folder)
            shutil.copytree(template_dir, folder)
            table.add_row(skill_name, "[green]UPDATED[/green]", f"{local_ver} -> {template_ver}")
            updates += 1
            continue

        table.add_row(skill_name, "[dim]OK[/dim]", f"Up to date ({local_ver})")

    console.print(table)
    if updates > 0:
        console.print(f"\n[green]Successfully updated {updates} skills.[/green]")
    else:
        console.print("\n[dim]All skills are up to date.[/dim]")
