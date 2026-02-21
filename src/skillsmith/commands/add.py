from pathlib import Path
import click
from . import (
    console, 
    find_template_skill_dir,
    download_github_dir
)

@click.command()
@click.argument("name_or_url")
def add_command(name_or_url):
    """Add a skill from local library or GitHub URL"""
    cwd = Path.cwd()
    dest_dir = cwd / ".agent" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if name_or_url.startswith("http"):
        # Remote fetch logic
        url = name_or_url
        name = url.split("/")[-1]
        target = dest_dir / name
        
        with console.status(f"[bold green]Downloading {name} from GitHub..."):
            try:
                download_github_dir(url, target)
                console.print(f"[green][OK][/green] Added skill: {name} (from GitHub)")
            except Exception as e:
                console.print(f"[red]Error downloading skill: {e}[/red]")
    else:
        # Local lookup
        skill_name = name_or_url
        src_dir = find_template_skill_dir(skill_name)
        
        if src_dir:
            target = dest_dir / skill_name
            if target.exists():
                console.print(f"[yellow][SKIP][/yellow] Skill '{skill_name}' already exists in .agent/skills/")
                return
                
            shutil.copytree(src_dir, target)
            console.print(f"[green][OK][/green] Added skill: {skill_name}")
        else:
            console.print(f"[red]Error: Skill '{skill_name}' not found. Use 'skillsmith list' to see available skills.[/red]")
