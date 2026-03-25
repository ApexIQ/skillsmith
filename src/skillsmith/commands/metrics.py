from pathlib import Path
import click
from rich.table import Table
from . import console
from .lockfile import load_lockfile

@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--export", type=click.Path(), help="Export metrics as JSON to the specified file path.")
def metrics_command(path, export):
    """Show skill quality and usage metrics from the current project."""
    import json
    cwd = Path(path).resolve()
    payload = load_lockfile(cwd)
    skills = payload.get("skills", [])
    
    if not skills:
        console.print("[yellow]No skills found in the current lockfile. Try 'skillsmith add' to installation skills.[/yellow]")
        return

    # Export Logic
    if export:
        export_path = Path(export)
        from datetime import datetime
        export_data = {
            "project_name": cwd.name,
            "timestamp": datetime.now().isoformat() + "Z",
            "total_skills": len(skills),
            "skills": [
                {
                    "name": s.get("name"),
                    "version": s.get("version"),
                    "metrics": s.get("metrics", {})
                } for s in skills
            ]
        }
        export_path.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
        console.print(f"[green][OK][/green] Metrics exported to: {export_path.name}")
        return

    table = Table(title=f"Skill Quality Metrics - {cwd.name}")
    table.add_column("Skill", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("Success Rate", justify="right")
    table.add_column("Applied", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Last Used", style="dim")

    for entry in skills:
        metrics = entry.get("metrics", {})
        success_rate = metrics.get("success_rate", 0.0)
        
        # Color code success rate
        sr_text = f"{success_rate:.2%}"
        if success_rate >= 0.9:
            sr_text = f"[green]{sr_text}[/green]"
        elif success_rate >= 0.7:
            sr_text = f"[yellow]{sr_text}[/yellow]"
        else:
            sr_text = f"[red]{sr_text}[/red]"
            
        applied = metrics.get("applied_count", 0)
        avg_tokens = metrics.get("avg_token_cost", 0.0)
        last_used = metrics.get("last_used_at") or "Never"
        
        table.add_row(
            entry.get("name", "unknown"),
            entry.get("version", "0.0.0"),
            sr_text,
            str(applied),
            f"{avg_tokens:,.0f}",
            last_used.split("T")[0] if "T" in last_used else last_used
        )

    console.print(table)
    console.print("\n[dim]Metics are updated automatically after every 'skillsmith compose' run.[/dim]")
