from __future__ import annotations

import json
from pathlib import Path

import click
from rich.table import Table

from . import console
from .autonomy_runtime import load_latest_session, run_autonomy_session, summarize_session


def _render_summary(summary: dict) -> None:
    table = Table(title="Autonomous Session")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Session", str(summary.get("session_id", "")))
    table.add_row("Domain", str(summary.get("domain", "")))
    table.add_row("Status", str(summary.get("status", "")))
    table.add_row("Stop reason", str(summary.get("stop_reason", "")))
    table.add_row("Iterations", str(summary.get("iterations", 0)))
    table.add_row("Kept", str(summary.get("kept", 0)))
    table.add_row("Discarded", str(summary.get("discarded", 0)))
    table.add_row("Crashed", str(summary.get("crashed", 0)))
    table.add_row("Best score", str(summary.get("best_score", 0)))
    table.add_row("Final score", str(summary.get("final_score", 0)))
    table.add_row("Benchmark", str(summary.get("benchmark_pack", "")))
    console.print(table)


@click.group(name="autonomous")
def autonomous_command():
    """Run bounded autonomous optimization loops."""


@autonomous_command.command("run")
@click.option("--domain", type=click.Choice(["recommend"]), default="recommend", show_default=True)
@click.option("--benchmark", "benchmark_pack", default=None, help="Benchmark pack file/name.")
@click.option("--max-hours", default=6.0, type=float, show_default=True)
@click.option("--max-iterations", default=30, type=int, show_default=True)
@click.option("--early-stop-fails", default=8, type=int, show_default=True)
@click.option("--score-gate", default=60.0, type=float, show_default=True)
@click.option("--recommendation-limit", default=5, type=int, show_default=True)
@click.option("--strict-gate/--no-strict-gate", default=True, show_default=True)
@click.option("--auto-evolve", is_flag=True, default=False, help="Trigger skill repair on benchmark regressions.")
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON output.")
def autonomous_run_command(
    domain: str,
    benchmark_pack: str | None,
    max_hours: float,
    max_iterations: int,
    early_stop_fails: int,
    score_gate: float,
    recommendation_limit: int,
    strict_gate: bool,
    auto_evolve: bool,
    json_output: bool,
):
    """Run an autonomous optimization session."""
    session = run_autonomy_session(
        cwd=Path.cwd(),
        domain=domain,
        benchmark_pack=benchmark_pack,
        max_iterations=max_iterations,
        max_hours=max_hours,
        max_non_improving=early_stop_fails,
        score_gate=score_gate,
        recommendation_limit=recommendation_limit,
        strict_gate=strict_gate,
        auto_evolve=auto_evolve,
    )
    summary = summarize_session(session)
    if json_output:
        click.echo(json.dumps({"session": session, "summary": summary}, indent=2))
        return
    _render_summary(summary)
    return session


@autonomous_command.command("status")
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON output.")
def autonomous_status_command(json_output: bool):
    """Show latest autonomy session status."""
    session = load_latest_session(Path.cwd())
    if not isinstance(session, dict):
        payload = {"available": False, "message": "No autonomy session found."}
        if json_output:
            click.echo(json.dumps(payload, indent=2))
            return
        console.print("[yellow]No autonomy session found.[/yellow]")
        return payload
    summary = summarize_session(session)
    if json_output:
        click.echo(json.dumps({"available": True, "session": session, "summary": summary}, indent=2))
        return
    _render_summary(summary)
    return summary


@autonomous_command.command("report")
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON output.")
def autonomous_report_command(json_output: bool):
    """Show autonomy summary report from latest session."""
    session = load_latest_session(Path.cwd())
    if not isinstance(session, dict):
        payload = {"available": False, "message": "No autonomy session found."}
        if json_output:
            click.echo(json.dumps(payload, indent=2))
            return
        console.print("[yellow]No autonomy session found.[/yellow]")
        return payload
    summary = summarize_session(session)
    if json_output:
        click.echo(json.dumps({"available": True, "summary": summary}, indent=2))
        return
    _render_summary(summary)
    return summary
