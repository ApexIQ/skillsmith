import click
from pathlib import Path
from . import console

@click.command(name="cookbook")
def cookbook_command():
    """Access the Skillsmith Mission Cookbook for complex recipes."""
    cwd = Path.cwd()
    cookbook_path = cwd / "docs" / "COOKBOOK.md"
    
    if cookbook_path.exists():
        console.print(f"[green][OK][/green] Mission Cookbook found at: [bold]{cookbook_path.relative_to(cwd)}[/bold]")
        console.print("\n[bold]Preview of Recipes:[/bold]")
        lines = cookbook_path.read_text(encoding="utf-8").splitlines()
        for line in lines[:20]:
            if line.startswith("### "):
                console.print(f"  [cyan]Recipe:[/cyan] {line[4:]}")
        console.print("\n[dim]Open the file in your IDE for the full step-by-step recipes.[/dim]")
    else:
        console.print("[yellow][WARN][/yellow] Mission Cookbook (docs/COOKBOOK.md) not found in current directory.")
        console.print("[dim]Generating a fresh copy...[/dim]")
        # We could trigger the rendering logic here if needed
