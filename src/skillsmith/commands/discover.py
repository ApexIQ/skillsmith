from pathlib import Path

import click
from rich.table import Table

from . import console
from .providers import (
    DiscoveryError,
    build_provider_registry,
    discover_skills_with_diagnostics,
    explain_candidate,
    get_profile,
    PROVIDER_SOURCE_ORDER,
)


def discover_skills(query: str, cwd: Path, source: str = "all", limit: int = 10):
    results, diagnostics = discover_skills_with_diagnostics(query, cwd, source=source, limit=limit)
    setattr(discover_skills, "_last_diagnostics", diagnostics)
    telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
    setattr(discover_skills, "_last_telemetry", telemetry)
    return results


@click.command()
@click.argument("query")
@click.option(
    "--source",
    type=click.Choice(["all", *PROVIDER_SOURCE_ORDER]),
    default="all",
    show_default=True,
    help="Discovery source",
)
@click.option("--limit", default=10, show_default=True, help="Maximum number of results")
def discover_command(query, source, limit):
    """Search local and remote skill providers for relevant skills."""
    cwd = Path.cwd()
    profile = get_profile(cwd)
    try:
        results = discover_skills(query, cwd, source=source, limit=limit)
        diagnostics = getattr(discover_skills, "_last_diagnostics", [])
        telemetry = getattr(discover_skills, "_last_telemetry", [])
    except DiscoveryError as exc:
        console.print(f"[red][!!][/red] {exc}")
        return

    if diagnostics:
        for item in diagnostics:
            console.print(f"[yellow][WARN][/yellow] {item}")
    if telemetry:
        for item in telemetry:
            console.print(
                f"[dim]telemetry provider={item.get('provider')} status={item.get('status')} "
                f"attempts={item.get('attempts')} elapsed_ms={item.get('elapsed_ms')} "
                f"error_type={item.get('error_type') or 'none'}[/dim]"
            )
    if not results:
        console.print("[yellow]No skills found for that query.[/yellow]")
        return

    table = Table(title=f"Discovered Skills ({len(results)})")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Category", style="magenta")
    table.add_column("Trust", justify="right")
    table.add_column("Why", style="yellow")
    table.add_column("Install", style="dim")
    table.add_column("Description", style="white")

    for item in results:
        explanation = explain_candidate(item, query, profile)
        table.add_row(
            item.name,
            item.source,
            item.category,
            str(item.trust_score),
            "; ".join(explanation["reasons"][:2]),
            item.install_ref,
            item.description[:80] + "..." if len(item.description) > 80 else item.description,
        )

    console.print(table)
    if source == "all":
        providers = ", ".join(build_provider_registry().keys())
        console.print(f"\n[dim]Searched providers: {providers}[/dim]")
    if profile:
        console.print(
            f"[dim]Profile: {profile.get('app_type', 'project')} | tools: {', '.join(profile.get('target_tools', [])) or 'none'}[/dim]"
        )
