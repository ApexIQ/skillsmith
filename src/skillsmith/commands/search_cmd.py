import click
import requests
import json
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from . import console

INDEX_URL = "https://raw.githubusercontent.com/ApexIQ/skillsmith/ghost-content/skills_index.json"

@click.command(name="search")
@click.argument("query", required=False)
@click.option("--category", help="Filter by exact category name")
@click.option("--limit", default=20, help="Maximum number of results to display")
@click.option("--categories", is_flag=True, help="List all available categories instead of skills")
def search_command(query, category, limit, categories):
    """Search and discover intelligence from the global Awesome Skills ecosystem."""
    
    with console.status("[cyan]Fetching global index from awesome-skills ecosystem...[/cyan]"):
        try:
            response = requests.get(INDEX_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            console.print(f"[red]Error fetching remote index:[/red] {e}")
            console.print("[dim]Please check your internet connection and try again.[/dim]")
            return

    # If --categories flag is present, display a tree of categories.
    if categories:
        cats = {}
        for skill in data:
            c = skill.get("category", "Uncategorized")
            cats[c] = cats.get(c, 0) + 1
            
        tree = Tree("[bold cyan]Global Ecosystem Categories[/bold cyan]")
        for c in sorted(cats.keys()):
            count = cats[c]
            tree.add(f"[green]{c}[/green] [dim]({count} skills)[/dim]")
            
        console.print(Panel(tree, title="Skill Taxonomy", border_style="blue"))
        console.print(f"[dim]Run `skillsmith search --category <name>` to view skills in a specific category.[/dim]")
        return

    # Filter by query and category
    results = []
    
    # Process query
    q = query.lower() if query else None
    
    for skill in data:
        # Category filter
        if category and skill.get("category", "").lower() != category.lower():
            continue
            
        # Keyword search
        if q:
            searchable = f"{skill.get('name', '')} {skill.get('description', '')} {skill.get('category', '')}".lower()
            if q not in searchable:
                continue
                
        results.append(skill)
        
    if not results:
        console.print(f"[yellow]No skills found matching your criteria.[/yellow]")
        return
        
    # Sort results to have well-defined ordering
    results.sort(key=lambda x: x.get("category", ""))
    
    limited_results = results[:limit]
    
    table = Table(title=f"Ecosystem Discovery ({len(results)} found, showing {len(limited_results)})", show_header=True, header_style="bold magenta")
    table.add_column("Skill ID", style="cyan", no_wrap=True)
    table.add_column("Category", style="green")
    table.add_column("Description", style="white")

    for s in limited_results:
        desc = s.get("description", "")
        if len(desc) > 80:
            desc = desc[:77] + "..."
        table.add_row(
            s.get("id", "unknown"),
            s.get("category", "unknown"),
            desc
        )

    console.print(table)
    
    if len(results) > limit:
        console.print(f"[dim]... and {len(results) - limit} more. Use --limit to see more results.[/dim]")
    
    console.print("\n[dim]To add a skill, run:[/dim] [bold cyan]skillsmith add --remote awesome <skill_id>[/bold cyan]")
