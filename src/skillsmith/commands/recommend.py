from pathlib import Path

import click
from rich.table import Table

from . import console
from .init import _infer_project_profile
from .providers import explain_recommendations_for_profile, get_profile


def _current_profile(cwd: Path) -> tuple[dict, bool]:
    profile = get_profile(cwd)
    if profile:
        return profile, False
    return _infer_project_profile(cwd), True


@click.command()
@click.option("--limit", default=5, show_default=True, help="Maximum number of recommendations to preview")
def recommend_command(limit):
    """Preview recommended skills for the current repo/profile before installing them."""
    cwd = Path.cwd()
    profile, inferred = _current_profile(cwd)
    recommendations = explain_recommendations_for_profile(profile, cwd, limit=limit)

    if not recommendations:
        console.print("[yellow]No recommendations available for the current project.[/yellow]")
        return

    table = Table(title=f"Recommended Skills ({len(recommendations)})")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Trust", justify="right")
    table.add_column("Pack", style="magenta")
    table.add_column("Why", style="yellow")
    table.add_column("Install", style="dim")
    table.add_column("Description", style="white")

    for candidate, explanation in recommendations:
        pack = "starter" if candidate.metadata.get("starter_pack") else ""
        table.add_row(
            candidate.name,
            candidate.source,
            str(candidate.trust_score),
            pack,
            "; ".join(explanation["reasons"][:2]),
            candidate.install_ref,
            candidate.description[:80] + "..." if len(candidate.description) > 80 else candidate.description,
        )

    console.print(table)
    console.print(
        f"[dim]Profile: {profile.get('app_type', 'project')} | tools: {', '.join(profile.get('target_tools', [])) or 'none'}[/dim]"
    )
    if inferred:
        console.print("[dim]Profile was inferred from repo signals because .agent/project_profile.yaml was missing.[/dim]")
