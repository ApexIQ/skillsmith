from pathlib import Path
import json
import click
from rich.table import Table
from . import (
    console, 
    iter_skill_dirs, 
    load_catalog
)

@click.command(name="list")
@click.option("--category", help="Filter by category")
@click.option("--tag", help="Filter by tag")
@click.option("--categories", "list_categories", is_flag=True, help="List all categories and skill counts")
def list_command(category, tag, list_categories):
    """List available skills from the catalog (650+ skills)."""
    catalog = load_catalog()
    
    if not catalog:
        console.print("[red]Error: skill_catalog.json not found. Run 'skillsmith rebuild' to create it.[/red]")
        return
        
    # Catalog is a list in v0.6.0+
    if isinstance(catalog, dict):
        # Legacy support
        skills = catalog.get("skills", {}).values()
    else:
        skills = catalog

    if list_categories:
        counts = {}
        for s in skills:
            cat = s.get("category", "uncategorized")
            counts[cat] = counts.get(cat, 0) + 1
        
        table = Table(title="Skill Categories")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="bold")
        for cat in sorted(counts.keys()):
            table.add_row(cat, str(counts[cat]))
        console.print(table)
        return

    table = Table(title=f"Available Skills ({len(skills)})")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Category", style="green")
    table.add_column("Description", style="white")

    count = 0
    for s in skills:
        if category and s.get("category") != category:
            continue
        if tag and tag.lower() not in [t.lower() for t in s.get("tags", [])]:
            continue
            
        table.add_row(
            s.get("name", "unknown"),
            s.get("version", "0.0.0"),
            s.get("category", "general"),
            s.get("description", "")[:80] + "..." if len(s.get("description", "")) > 80 else s.get("description", "")
        )
        count += 1

    console.print(table)
    console.print(f"\n[dim]Showing {count} matching skills.[/dim]")
