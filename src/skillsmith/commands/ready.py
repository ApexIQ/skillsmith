from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import click

from ..api import compose_workflow, init_project
from . import console, sanitize_json
from .doctor import _doctor_machine_summary
from .report import _build_report
from ..readiness_artifacts import render_readiness_pr


DEFAULT_READY_GOAL = "make this repository agent-ready safely in under 10 minutes"
READY_CONTEXT_INDEX_RELATIVE_PATH = ".agent/context/index.json"
READY_GITHUB_WORKFLOW_RELATIVE_PATH = ".github/workflows/skillsmith-ready.yml"
READY_GITHUB_WORKFLOW_MARKER = "# Managed by `skillsmith ready ci --emit github`."
READY_ARTIFACT_DIR = ".agent/reports/readiness"


def _step_summary(name: str, *, ok: bool, exit_code: int, error: str | None = None, **data: object) -> dict[str, object]:
    payload = {"name": name, "ok": ok, "exit_code": exit_code}
    if error:
        payload["error"] = error
    payload.update(data)
    return payload


def _doctor_summary(payload: dict[str, object] | None, *, exit_code: int, error: str | None) -> dict[str, object]:
    if not payload:
        return _step_summary("doctor", ok=False, exit_code=exit_code, error=error or "doctor summary unavailable")
    failing_checks = payload.get("readiness_failing_checks", [])
    return _step_summary(
        "doctor",
        ok=bool(payload.get("ok", False)),
        exit_code=exit_code,
        error=error,
        score=int(payload.get("readiness_score", 0) or 0),
        total_checks=int(payload.get("readiness_total_checks", 0) or 0),
        passing_checks=int(payload.get("readiness_passing_checks", 0) or 0),
        failing_checks=failing_checks if isinstance(failing_checks, list) else [],
        missing=list(payload.get("missing", [])) if isinstance(payload.get("missing", []), list) else [],
        stale=list(payload.get("stale", [])) if isinstance(payload.get("stale", []), list) else [],
    )


def _compose_summary(payload: dict[str, object] | None, *, exit_code: int, error: str | None) -> dict[str, object]:
    if not payload:
        return _step_summary("compose", ok=False, exit_code=exit_code, error=error or "compose summary unavailable")
    workflow = payload.get("workflow", {})
    if not isinstance(workflow, dict):
        workflow = {}
    selected_skills = workflow.get("skills", [])
    if not isinstance(selected_skills, list):
        selected_skills = []
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    return _step_summary(
        "compose",
        ok=bool(payload.get("ok", False)),
        exit_code=exit_code,
        error=error,
        goal=str(payload.get("goal", "")),
        selected_skills=[str(skill) for skill in selected_skills],
        workflow_steps=len(steps),
        trace_path=payload.get("trace_path"),
    )


def _report_summary(
    report_payload: dict[str, object] | None,
    snippet: str,
    *,
    exit_code: int,
    error: str | None,
) -> dict[str, object]:
    readiness = {}
    if isinstance(report_payload, dict):
        readiness = report_payload.get("readiness_summary", {}) if isinstance(report_payload.get("readiness_summary", {}), dict) else {}
    return _step_summary(
        "report",
        ok=bool(readiness.get("ready", False)) if readiness else False,
        exit_code=exit_code,
        error=error,
        profile_source=str(report_payload.get("profile_source", "unknown")) if isinstance(report_payload, dict) else "unknown",
        starter_pack_label=str(report_payload.get("starter_pack_label", "")) if isinstance(report_payload, dict) else "",
        readiness_summary=readiness,
        snippet=snippet,
    )


def _build_readiness_summary(
    *,
    guided_init: bool,
    init_step: dict[str, object],
    doctor_step: dict[str, object],
    compose_step: dict[str, object],
    report_step: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    warnings: list[str] = []

    if guided_init and not init_step["ok"]:
        blockers.append("guided init failed")

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


def _context_index_path(cwd: Path) -> Path:
    return cwd / ".agent" / "context" / "index.json"


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _context_index_needs_fix(cwd: Path) -> bool:
    payload = _load_json_file(_context_index_path(cwd))
    if not isinstance(payload, dict):
        return True
    files = payload.get("files", [])
    return not isinstance(files, list)


def _ready_context_entries(cwd: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seed_files = [
        ("AGENTS.md", "Core agent instructions and execution contract."),
        (".agent/PROJECT.md", "Project vision and architecture summary."),
        (".agent/ROADMAP.md", "Strategic milestones and delivery sequencing."),
        (".agent/STATE.md", "Current tactical state and recent changes."),
        (".agent/project_profile.yaml", "Structured project profile for managed outputs."),
        (".agent/context/project-context.md", "Generated project context snapshot."),
    ]
    for relative_path, summary in seed_files:
        path = cwd / Path(relative_path)
        if not path.exists():
            continue
        entries.append(
            {
                "path": relative_path,
                "freshness_score": 100,
                "freshness_stamp": "ready-fix",
                "snippet": summary,
                "compressed_snippet": summary,
                "tier_snippets": {"l0": summary, "l1": summary, "l2": summary},
                "path_group": "agent-core",
            }
        )
    return entries


def _write_ready_context_index(cwd: Path) -> Path:
    path = _context_index_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _ready_context_entries(cwd)
    payload = {
        "version": 1,
        "generator": "skillsmith ready --fix",
        "generated_at": "ready-fix",
        "freshness_stamp": "ready-fix",
        "file_count": len(entries),
        "files": entries,
        "path_groups": [
            {
                "name": "agent-core",
                "paths": [entry["path"] for entry in entries],
                "compaction_hint": {
                    "compaction_mode": "preserve",
                    "preferred_tier": "l2",
                    "priority_rank": 1,
                },
            }
        ]
        if entries
        else [],
        "compaction_hints": {
            "agent-core": {
                "compaction_mode": "preserve",
                "preferred_tier": "l2",
                "priority_rank": 1,
            }
        }
        if entries
        else {},
        "retrieval_trace_dir": ".agent/context/traces",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _apply_ready_fixes(cwd: Path) -> list[dict[str, object]]:
    fixes: list[dict[str, object]] = []
    bootstrap_files = [
        cwd / "AGENTS.md",
        cwd / ".agent" / "project_profile.yaml",
        cwd / ".agent" / "context" / "project-context.md",
        cwd / ".agent" / "STATE.md",
    ]
    missing_bootstrap = [path for path in bootstrap_files if not path.exists()]
    if missing_bootstrap:
        init_result = init_project(cwd, minimal=True)
        fixes.append(
            {
                "name": "bootstrap",
                "ok": bool(init_result.get("ok", False)),
                "action": "skillsmith init --minimal",
                "changed": sorted(
                    str(path.relative_to(cwd)).replace("\\", "/")
                    for path in missing_bootstrap
                ),
                "exit_code": int(init_result.get("exit_code", 1) or 1),
                "details": str(init_result.get("output", "")).strip() or "bootstrap attempted",
            }
        )

    if _context_index_needs_fix(cwd):
        index_path = _write_ready_context_index(cwd)
        fixes.append(
            {
                "name": "context-index",
                "ok": True,
                "action": "write minimal context index",
                "changed": [index_path.relative_to(cwd).as_posix()],
                "details": "wrote deterministic minimal context index for readiness checks",
            }
        )

    return fixes


def _render_github_ready_workflow() -> str:
    return dedent(
        f"""\
        {READY_GITHUB_WORKFLOW_MARKER}
        # Re-run `skillsmith ready ci --emit github` to regenerate this file.
        name: Skillsmith Ready

        on:
          pull_request:
          push:
            branches: [main]

        jobs:
          readiness:
            runs-on: ubuntu-latest
            steps:
              - name: Checkout
                uses: actions/checkout@v4

              - name: Setup Python
                uses: actions/setup-python@v5
                with:
                  python-version: "3.11"

              - name: Install skillsmith from source
                run: |
                  python -m pip install --upgrade pip
                  python -m pip install .

              - name: Run readiness gate
                run: |
                  python -m skillsmith ready
                  python -m skillsmith report --artifact-dir {READY_ARTIFACT_DIR}

              - name: Upload readiness artifacts
                if: always()
                uses: actions/upload-artifact@v4
                with:
                  name: skillsmith-readiness
                  path: {READY_ARTIFACT_DIR}/
                  if-no-files-found: warn

              - name: Publish readiness summary
                if: always()
                shell: bash
                run: |
                  {{
                    echo "## Skillsmith Readiness"
                    if [ -f "{READY_ARTIFACT_DIR}/readiness_pr.md" ]; then
                      cat "{READY_ARTIFACT_DIR}/readiness_pr.md"
                    else
                      echo "- Readiness snippet not found. See uploaded artifacts."
                    fi
                  }} >> "$GITHUB_STEP_SUMMARY"
        """
    )


def _validate_github_ready_workflow(content: str) -> list[str]:
    required_tokens = [
        READY_GITHUB_WORKFLOW_MARKER,
        "name: Skillsmith Ready",
        "python -m skillsmith ready",
        f"python -m skillsmith report --artifact-dir {READY_ARTIFACT_DIR}",
        "uses: actions/upload-artifact@v4",
        "if: always()",
    ]
    missing = [token for token in required_tokens if token not in content]
    return missing


def _emit_github_ready_workflow(cwd: Path) -> dict[str, object]:
    workflow_path = cwd / READY_GITHUB_WORKFLOW_RELATIVE_PATH
    content = _render_github_ready_workflow()
    result = {
        "ok": True,
        "emit": "github",
        "path": workflow_path.as_posix(),
        "relative_path": READY_GITHUB_WORKFLOW_RELATIVE_PATH,
        "status": "created",
        "updated": True,
        "content": content,
        "managed": True,
    }

    if workflow_path.exists():
        existing = workflow_path.read_text(encoding="utf-8")
        if existing == content:
            missing = _validate_github_ready_workflow(existing)
            if missing:
                result["ok"] = False
                result["status"] = "invalid"
                result["updated"] = False
                result["managed"] = True
                result["validation_errors"] = missing
                result["error"] = (
                    f"{READY_GITHUB_WORKFLOW_RELATIVE_PATH} is managed but invalid; "
                    "re-run emit to repair the file"
                )
                return result
            result["status"] = "unchanged"
            result["updated"] = False
            result["validated"] = True
            return result
        if READY_GITHUB_WORKFLOW_MARKER not in existing:
            result["ok"] = False
            result["status"] = "refused"
            result["updated"] = False
            result["managed"] = False
            result["error"] = (
                f"{READY_GITHUB_WORKFLOW_RELATIVE_PATH} exists and is not managed by "
                "`skillsmith ready ci --emit github`; refusing to overwrite it"
            )
            return result
        result["status"] = "updated"

    missing = _validate_github_ready_workflow(content)
    if missing:
        result["ok"] = False
        result["status"] = "invalid"
        result["updated"] = False
        result["validation_errors"] = missing
        result["error"] = "generated workflow failed internal validation"
        return result

    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(content, encoding="utf-8")
    result["validated"] = True
    return result


def _run_ready_flow(goal: str, guided_init: bool, fix: bool) -> dict[str, object]:
    cwd = Path.cwd()
    fixes = _apply_ready_fixes(cwd) if fix else []

    init_step = _step_summary("init", ok=True, exit_code=0, ran=False, skipped=True)
    if guided_init:
        init_result = init_project(cwd, guided=True)
        init_step = _step_summary(
            "init",
            ok=bool(init_result.get("ok", False)),
            exit_code=int(init_result.get("exit_code", 1) or 1),
            ran=True,
            skipped=False,
            output=str(init_result.get("output", "")).strip(),
        )

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

    readiness_summary = _build_readiness_summary(
        guided_init=guided_init,
        init_step=init_step,
        doctor_step=doctor_step,
        compose_step=compose_step,
        report_step=report_step,
    )

    return sanitize_json(
        {
            "ok": readiness_summary["ready"],
            "goal": goal,
            "cwd": str(cwd),
            "guided_init_requested": guided_init,
            "fix_requested": fix,
            "fixes": fixes,
            "init": init_step,
            "doctor": doctor_step,
            "compose": compose_step,
            "report": report_step,
            "readiness_summary": readiness_summary,
        }
    )


def _print_human_summary(payload: dict[str, object]) -> None:
    console.print("[bold cyan]Skillsmith Ready[/bold cyan]")
    console.print(f"[dim]Goal: {payload['goal']}[/dim]")

    fixes = payload.get("fixes", [])
    init_step = payload["init"]
    doctor_step = payload["doctor"]
    compose_step = payload["compose"]
    report_step = payload["report"]
    readiness = payload["readiness_summary"]

    def marker(ok: bool) -> str:
        return "[green][OK][/green]" if ok else "[red][!!][/red]"

    if isinstance(fixes, list) and fixes:
        console.print("\n[bold]Fixes[/bold]")
        for item in fixes:
            if not isinstance(item, dict):
                continue
            console.print(
                f"  {marker(bool(item.get('ok', False)))} {item.get('name', 'fix')} - "
                f"{item.get('details', item.get('action', 'applied'))}"
            )

    console.print(
        f"\n[bold]Init[/bold]\n"
        f"  {marker(bool(init_step['ok']))} guided init {'ran' if init_step['ran'] else 'skipped'}"
        f" ({'ok' if init_step['ok'] else 'failed'})"
    )
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
    console.print()
    click.echo(report_step["snippet"])

    if not readiness["ready"]:
        console.print("\n[bold yellow][!!] Not ready yet. Fix the blockers above and re-run `skillsmith ready`.[/bold yellow]")
    else:
        console.print("\n[bold green][OK] Repo readiness flow completed.[/bold green]")


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--goal",
    default=DEFAULT_READY_GOAL,
    show_default=True,
    help="Goal to tailor the compose step in the readiness flow.",
)
@click.option(
    "--guided-init/--no-guided-init",
    default=False,
    show_default=True,
    help="Run `skillsmith init --guided` before the readiness checks.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Apply safe deterministic fixes for common readiness blockers before running the flow.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable readiness summary")
def ready_command(ctx: click.Context, goal: str, guided_init: bool, fix: bool, as_json: bool):
    """Run the single repo-readiness flow across init, doctor, compose, and report."""
    if ctx.invoked_subcommand is not None:
        return

    payload = _run_ready_flow(goal, guided_init, fix)

    if as_json:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["ok"]:
            raise click.exceptions.Exit(1)
        return

    _print_human_summary(payload)
    if not payload["ok"]:
        raise click.exceptions.Exit(1)


@ready_command.command("ci")
@click.option(
    "--emit",
    type=click.Choice(["github"], case_sensitive=False),
    required=True,
    help="Emit/update a deterministic CI workflow for the selected platform.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable output")
def ready_ci_command(emit: str, as_json: bool):
    """Emit CI-ready workflow scaffolding for readiness automation."""
    cwd = Path.cwd()

    if emit.lower() != "github":
        raise click.ClickException(f"Unsupported emit target: {emit}")

    payload = sanitize_json(_emit_github_ready_workflow(cwd))

    if as_json:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["ok"]:
            raise click.exceptions.Exit(1)
        return

    if not payload["ok"]:
        raise click.ClickException(str(payload.get("error", "failed to emit CI workflow")))

    console.print(
        f"[green][OK][/green] {payload['status'].capitalize()} "
        f"{payload['relative_path']}"
    )
    click.echo(str(payload["content"]))
