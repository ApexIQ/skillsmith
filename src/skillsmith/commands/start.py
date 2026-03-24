from __future__ import annotations

import json
from pathlib import Path

import click

from ..api import compose_workflow, init_project
from ..readiness_artifacts import render_readiness_pr
from . import console, sanitize_json
from .doctor import _doctor_machine_summary
from .ready import DEFAULT_READY_GOAL, _compose_summary, _doctor_summary, _report_summary, _step_summary
from .report import _build_report


def _bootstrap_artifacts_present(cwd: Path) -> bool:
    return all(
        (
            (cwd / "AGENTS.md").exists(),
            (cwd / ".agent" / "project_profile.yaml").exists(),
            (cwd / ".agent" / "context" / "project-context.md").exists(),
        )
    )


def _run_bootstrap(cwd: Path) -> dict[str, object]:
    if _bootstrap_artifacts_present(cwd):
        return _step_summary(
            "init",
            ok=True,
            exit_code=0,
            ran=False,
            skipped=True,
            mode="existing",
            command="skillsmith init",
        )

    init_result = init_project(cwd)
    return _step_summary(
        "init",
        ok=bool(init_result.get("ok", False)),
        exit_code=int(init_result.get("exit_code", 1) or 1),
        ran=True,
        skipped=False,
        mode="auto",
        command=str(init_result.get("command", "skillsmith init")),
        output=str(init_result.get("output", "")).strip(),
        artifacts=init_result.get("artifacts", {}),
    )


def _build_start_readiness_summary(
    *,
    init_step: dict[str, object],
    doctor_step: dict[str, object],
    compose_step: dict[str, object],
    report_step: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    warnings: list[str] = []

    if init_step.get("ran") and not init_step["ok"]:
        blockers.append("bootstrap init failed")

    if not doctor_step["ok"]:
        failing_checks = doctor_step.get("failing_checks", [])
        if isinstance(failing_checks, list) and failing_checks:
            blockers.extend(str(item.get("name", "doctor check failed")) for item in failing_checks if isinstance(item, dict))
        else:
            blockers.append("doctor reported issues")

    if not compose_step["ok"]:
        blockers.append("compose did not produce a ready workflow")

    report_summary = report_step.get("readiness_summary", {})
    if isinstance(report_summary, dict):
        blockers.extend(str(item) for item in report_summary.get("blockers", []) if item)
        warnings.extend(str(item) for item in report_summary.get("warnings", []) if item)

    ready = bool(
        report_summary.get("ready", False)
        if isinstance(report_summary, dict)
        else False
    ) and bool(init_step["ok"]) and bool(doctor_step["ok"]) and bool(compose_step["ok"])

    score = int(report_summary.get("score", 0) or 0) if isinstance(report_summary, dict) else 0
    status = "ready" if ready else "needs_attention"
    summary = str(report_summary.get("summary", "needs attention")) if isinstance(report_summary, dict) else "needs attention"

    return {
        "ready": ready,
        "status": status,
        "score": score,
        "summary": summary,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _print_start_human_summary(payload: dict[str, object]) -> None:
    console.print("[bold cyan]Skillsmith Start[/bold cyan]")
    console.print("[dim]Default path: init -> doctor -> compose -> report[/dim]")
    console.print(f"[dim]Goal: {payload['goal']}[/dim]")

    init_step = payload["init"]
    doctor_step = payload["doctor"]
    compose_step = payload["compose"]
    report_step = payload["report"]
    readiness = payload["readiness_summary"]

    def marker(ok: bool) -> str:
        return "[green][OK][/green]" if ok else "[red][!!][/red]"

    init_label = "bootstrap init ran" if init_step["ran"] else "bootstrap init skipped"
    init_mode = str(init_step.get("mode", "auto"))
    console.print(
        f"\n[bold]Bootstrap[/bold]\n"
        f"  {marker(bool(init_step['ok']))} {init_label} ({init_mode})"
    )
    if init_step.get("command"):
        console.print(f"  [dim]Command: {init_step['command']}[/dim]")
    if init_step.get("error"):
        console.print(f"  [yellow][!!][/yellow] {init_step['error']}")

    console.print(
        f"\n[bold]Doctor[/bold]\n"
        f"  {marker(bool(doctor_step['ok']))} score {doctor_step['score']}/100 "
        f"({doctor_step['passing_checks']}/{doctor_step['total_checks']} checks passed)"
    )
    if doctor_step.get("failing_checks"):
        for item in doctor_step["failing_checks"]:
            if isinstance(item, dict):
                console.print(f"  [yellow][!!][/yellow] {item.get('name', 'check')} - {item.get('details', '')}")
    if doctor_step.get("error"):
        console.print(f"  [yellow][!!][/yellow] {doctor_step['error']}")

    console.print(
        f"\n[bold]Compose[/bold]\n"
        f"  {marker(bool(compose_step['ok']))} {len(compose_step['selected_skills'])} skills, "
        f"{compose_step['workflow_steps']} workflow steps"
    )
    if compose_step.get("trace_path"):
        console.print(f"  [dim]Trace: {compose_step['trace_path']}[/dim]")
    if compose_step.get("error"):
        console.print(f"  [yellow][!!][/yellow] {compose_step['error']}")

    console.print(
        f"\n[bold]Report[/bold]\n"
        f"  {marker(bool(readiness['ready']))} {readiness['status'].replace('_', ' ')} "
        f"({readiness['score']}/100)"
    )
    if readiness.get("blockers"):
        console.print("  [yellow][!!][/yellow] Blockers:")
        for item in readiness["blockers"]:
            console.print(f"    - {item}")
    if readiness.get("warnings"):
        console.print("  [yellow][!!][/yellow] Warnings:")
        for item in readiness["warnings"]:
            console.print(f"    - {item}")

    console.print("\n[bold]Readiness Snippet[/bold]")
    click.echo(report_step["snippet"])
    console.print("\n[dim]Persist artifacts with `skillsmith report --artifact-dir .agent/readiness`.[/dim]")

    if not readiness["ready"]:
        console.print("[bold yellow][!!] Not ready yet. Fix the blockers above and re-run `skillsmith start`.[/bold yellow]")
    else:
        console.print("[bold green][OK] Default wedge path completed.[/bold green]")


@click.command()
@click.option(
    "--goal",
    default=DEFAULT_READY_GOAL,
    show_default=True,
    help="Goal to tailor the compose step in the default wedge path.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable start summary")
def start_command(goal: str, as_json: bool):
    """Run the default bootstrap-to-readiness wedge path in one command."""
    cwd = Path.cwd()

    init_step = _run_bootstrap(cwd)

    doctor_error = None
    doctor_payload = None
    try:
        doctor_payload = _doctor_machine_summary(cwd, strict=False)
    except Exception as exc:
        doctor_error = str(exc)
    doctor_step = _doctor_summary(
        doctor_payload,
        exit_code=0 if doctor_payload is not None else 1,
        error=doctor_error,
    )

    compose_error = None
    compose_payload = None
    try:
        compose_payload = compose_workflow(goal, cwd)
    except Exception as exc:
        compose_error = str(exc)
    compose_step = _compose_summary(
        compose_payload,
        exit_code=0 if compose_payload and compose_payload.get("ok", False) else 1,
        error=compose_error,
    )

    report_payload = None
    report_error = None
    report_snippet = ""
    try:
        report_payload = sanitize_json(_build_report(cwd))
        report_snippet = render_readiness_pr(report_payload)
    except Exception as exc:
        report_error = str(exc)
    report_step = _report_summary(
        report_payload,
        report_snippet,
        exit_code=0 if report_payload is not None else 1,
        error=report_error,
    )

    readiness_summary = _build_start_readiness_summary(
        init_step=init_step,
        doctor_step=doctor_step,
        compose_step=compose_step,
        report_step=report_step,
    )

    payload = sanitize_json(
        {
            "ok": readiness_summary["ready"],
            "goal": goal,
            "cwd": str(cwd),
            "guided_init_requested": False,
            "init": init_step,
            "doctor": doctor_step,
            "compose": compose_step,
            "report": report_step,
            "readiness_summary": readiness_summary,
        }
    )

    if as_json:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["ok"]:
            raise click.exceptions.Exit(1)
        return

    _print_start_human_summary(payload)
    if not payload["ok"]:
        raise click.exceptions.Exit(1)
