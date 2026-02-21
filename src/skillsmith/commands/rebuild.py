from pathlib import Path
import json
import yaml
import click
from . import (
    console, 
    iter_skill_dirs, 
    TEMPLATE_DIR,
    sanitize_json
)

@click.command()
@click.option("--dir", "skill_dir", type=click.Path(exists=True, file_okay=False), help="Directory to scan for skills")
@click.option("--output", type=click.Path(), help="Output path for skill_catalog.json")
def rebuild_command(skill_dir, output):
    """Rebuild the skill catalog from the skills directory."""
    if not skill_dir:
        skill_dir = TEMPLATE_DIR / ".agent" / "skills"
    else:
        skill_dir = Path(skill_dir)
        
    if not output:
        output = TEMPLATE_DIR / ".agent" / "skill_catalog.json"
    else:
        output = Path(output)
    
    catalog = []
    
    with console.status(f"[bold green]Scanning {skill_dir}..."):
        for folder in iter_skill_dirs(skill_dir):
            md_file = folder / "SKILL.md"
            
            try:
                content = md_file.read_text(encoding="utf-8")
                parts = content.split("---")
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    
                    # Fix JSON serialization for dates recursively
                    meta = sanitize_json(meta)
                            
                    if "name" not in meta:
                        meta["name"] = folder.name
                    
                    # Auto-detect category from parent folder
                    if "category" not in meta:
                        parent_name = folder.parent.name
                        if parent_name != "skills" and parent_name != ".agent":
                             meta["category"] = parent_name
                             
                    catalog.append(meta)
            except Exception as e:
                console.print(f"[red]Error parsing {md_file}: {e}[/red]")

    output.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    console.print(f"[green]Successfully rebuilt catalog with {len(catalog)} skills at {output}[/green]")
