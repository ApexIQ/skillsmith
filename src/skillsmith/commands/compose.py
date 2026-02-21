import yaml
from pathlib import Path
import click
from . import (
    console, 
    load_catalog
)

@click.command()
@click.argument("goal")
@click.option("--max-skills", default=5, help="Maximum skills to include")
@click.option("--output", type=click.Path(), help="Output file (default: stdout)")
def compose_command(goal, max_skills, output):
    """Generate a workflow by composing relevant skills for a given GOAL."""
    catalog = load_catalog()
    if not catalog:
        console.print("[red]Error: skill_catalog.json not found.[/red]")
        return
        
    # Simple semantic scoring (keyword-based)
    keywords = goal.lower().split()
    scored = []
    
    # Catalog is a list in v0.6.0+
    skills = catalog if isinstance(catalog, list) else catalog.get("skills", {}).values()

    for s in skills:
        score = 0
        text = (s.get("name", "") + " " + s.get("description", "") + " " + " ".join(s.get("tags", []))).lower()
        for kw in keywords:
            if kw in text:
                score += 1
        if score > 0:
            scored.append((score, s))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_skills]
    
    if not top:
        console.print("[yellow]No relevant skills found for that goal.[/yellow]")
        return
        
    workflow = {
        "goal": goal,
        "skills": [s[1]["name"] for s in top],
        "steps": [f"Execute task with {s[1]['name']}" for s in top]
    }
    
    yaml_out = yaml.dump(workflow, sort_keys=False)
    if output:
        Path(output).write_text(yaml_out, encoding="utf-8")
        console.print(f"[green][OK][/green] Workflow written to {output}")
    else:
        console.print("\n[bold]--- Generated Workflow ---[/bold]")
        console.print(yaml_out)
