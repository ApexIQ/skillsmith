from pathlib import Path
import json

import click
from rich.table import Table

from . import console
from .init import _infer_project_profile
from .providers import candidate_allowed, explain_recommendations_for_profile, get_profile


def _current_profile(cwd: Path) -> tuple[dict, bool]:
    profile = get_profile(cwd)
    if profile:
        return profile, False
    return _infer_project_profile(cwd), True


def _recommendation_entry(candidate, explanation: dict, profile: dict) -> dict:
    allowed, reason = candidate_allowed(candidate, profile)
    return {
        "name": candidate.name,
        "source": candidate.source,
        "version": candidate.version,
        "category": candidate.category,
        "trust_score": candidate.trust_score,
        "popularity_score": candidate.popularity_score,
        "freshness_score": candidate.freshness_score,
        "compatibility": list(candidate.compatibility),
        "install_ref": candidate.install_ref,
        "description": candidate.description,
        "starter_pack": bool(candidate.metadata.get("starter_pack")),
        "starter_pack_label": candidate.metadata.get("starter_pack_label", ""),
        "explanation": {
            "reasons": list(explanation.get("reasons", [])),
            "matched_query": list(explanation.get("matched_query", [])),
            "matched_profile": list(explanation.get("matched_profile", [])),
            "source_bonus": explanation.get("source_bonus", 0),
            "profile_bonus": explanation.get("profile_bonus", 0),
            "metadata_bonus": explanation.get("metadata_bonus", 0),
            "freshness_source": explanation.get("freshness_source", ""),
            "license": explanation.get("license", ""),
            "maintainer": explanation.get("maintainer", ""),
        },
        "eligibility": {
            "passed": bool(allowed),
            "reason": reason,
        },
    }


def _recommendations_payload(profile: dict, inferred: bool, recommendations: list[tuple], limit: int) -> dict:
    items = [_recommendation_entry(candidate, explanation, profile) for candidate, explanation in recommendations]
    return {
        "profile_source": "inferred" if inferred else "saved",
        "profile": profile,
        "limit": limit,
        "count": len(items),
        "recommendations": items,
    }


def _render_human(recommendations: list[tuple], profile: dict, inferred: bool, *, explain: bool) -> None:
    table = Table(title=f"Recommended Skills ({len(recommendations)})")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Trust", justify="right")
    table.add_column("Pack", style="magenta")
    table.add_column("Why", style="yellow")
    table.add_column("Install", style="dim")
    table.add_column("Description", style="white")
    if explain:
        table.add_column("Gate", style="red")

    for candidate, explanation in recommendations:
        pack = "starter" if candidate.metadata.get("starter_pack") else ""
        reasons = explanation.get("reasons", [])
        why = "; ".join(reasons if explain else reasons[:2])
        row = [
            candidate.name,
            candidate.source,
            str(candidate.trust_score),
            pack,
            why,
            candidate.install_ref,
            candidate.description[:80] + "..." if len(candidate.description) > 80 else candidate.description,
        ]
        if explain:
            allowed, reason = candidate_allowed(candidate, profile)
            row.append("passed" if allowed else f"failed: {reason}")
        table.add_row(*row)

    console.print(table)
    console.print(
        f"[dim]Profile: {profile.get('app_type', 'project')} | tools: {', '.join(profile.get('target_tools', [])) or 'none'}[/dim]"
    )
    if inferred:
        console.print("[dim]Profile was inferred from repo signals because .agent/project_profile.yaml was missing.[/dim]")
    if explain:
        for candidate, explanation in recommendations:
            allowed, reason = candidate_allowed(candidate, profile)
            gate = "passed" if allowed else f"failed: {reason}"
            console.print(
                "[dim]- "
                f"{candidate.name}: {gate}; "
                f"matched_query={', '.join(explanation.get('matched_query', [])) or 'none'}; "
                f"matched_profile={', '.join(explanation.get('matched_profile', [])) or 'none'}"
                "[/dim]"
            )


@click.command()
@click.option("--limit", default=5, show_default=True, help="Maximum number of recommendations to preview")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable recommendation output")
@click.option("--explain", is_flag=True, help="Show richer reasoning and gate details in human output")
def recommend_command(limit, as_json: bool, explain: bool):
    """Preview recommended skills for the current repo/profile before installing them."""
    cwd = Path.cwd()
    profile, inferred = _current_profile(cwd)
    recommendations = explain_recommendations_for_profile(profile, cwd, limit=limit)

    if as_json:
        click.echo(json.dumps(_recommendations_payload(profile, inferred, recommendations, limit), indent=2, sort_keys=True))
        return

    if not recommendations:
        console.print("[yellow]No recommendations available for the current project.[/yellow]")
        return

    _render_human(recommendations, profile, inferred, explain=explain)
