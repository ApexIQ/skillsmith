from __future__ import annotations

import subprocess
from pathlib import Path

import click
from rich.table import Table

from . import console
from .init import _infer_project_profile
from .lockfile import LOCKFILE_NAME, load_lockfile, verify_lockfile_signature
from .rendering import load_project_profile, managed_file_map


def _current_profile(cwd: Path) -> tuple[dict, str]:
    try:
        profile = load_project_profile(cwd)
        if isinstance(profile, dict) and profile:
            return profile, "saved"
    except Exception:
        pass
    return _infer_project_profile(cwd), "inferred"


def _git_status_summary(cwd: Path) -> dict:
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

    if probe.returncode != 0:
        return {"available": False, "reason": "not a git repository"}

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-b"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

    lines = [line.rstrip() for line in status.stdout.splitlines() if line.strip()]
    branch = ""
    dirty_lines: list[str] = []
    for line in lines:
        if line.startswith("## "):
            branch = line[3:].strip()
            continue
        dirty_lines.append(line)

    untracked = sum(1 for line in dirty_lines if line.startswith("?? "))
    staged_or_modified = len(dirty_lines) - untracked
    return {
        "available": True,
        "branch": branch,
        "dirty": bool(dirty_lines),
        "dirty_count": len(dirty_lines),
        "untracked_count": untracked,
        "modified_count": staged_or_modified,
        "status_lines": dirty_lines[:5],
        "clean": not dirty_lines,
    }


def _managed_drift_summary(cwd: Path, profile: dict) -> dict:
    expected = managed_file_map(cwd, profile)
    core_paths = [
        cwd / "AGENTS.md",
        cwd / ".agent" / "PROJECT.md",
        cwd / ".agent" / "ROADMAP.md",
        cwd / ".agent" / "STATE.md",
        cwd / ".agent" / "project_profile.yaml",
        cwd / ".agent" / "context" / "project-context.md",
    ]

    missing: list[str] = []
    drifted: list[str] = []
    for path in core_paths:
        expected_content = expected.get(path)
        if expected_content is None:
            continue
        if not path.exists():
            missing.append(path.relative_to(cwd).as_posix())
            continue
        actual_content = path.read_text(encoding="utf-8", errors="ignore")
        if actual_content.strip() != expected_content.strip():
            drifted.append(path.relative_to(cwd).as_posix())

    return {
        "missing": missing,
        "drifted": drifted,
        "has_drift": bool(missing or drifted),
    }


def _lockfile_summary(cwd: Path) -> dict:
    path = cwd / LOCKFILE_NAME
    payload = load_lockfile(cwd)
    skills = payload.get("skills", []) if isinstance(payload.get("skills"), list) else []
    signature = verify_lockfile_signature(payload)
    return {
        "present": path.exists(),
        "path": path.relative_to(cwd).as_posix(),
        "skill_count": len([item for item in skills if isinstance(item, dict)]),
        "signature_state": signature.get("state", "skipped"),
        "signature_valid": bool(signature.get("valid", True)),
        "signature_message": signature.get("message", ""),
    }


def _workflow_summary(cwd: Path) -> dict:
    workflow_dir = cwd / ".agent" / "workflows"
    files = sorted(path.name for path in workflow_dir.glob("*.md")) if workflow_dir.exists() else []
    return {
        "present": workflow_dir.exists(),
        "count": len(files),
        "names": files[:5],
    }


def _suggestions(cwd: Path) -> tuple[list[dict], dict]:
    profile, profile_source = _current_profile(cwd)
    profile_path = cwd / ".agent" / "project_profile.yaml"
    context_path = cwd / ".agent" / "context" / "project-context.md"
    git_status = _git_status_summary(cwd)
    drift = _managed_drift_summary(cwd, profile)
    lockfile = _lockfile_summary(cwd)
    workflows = _workflow_summary(cwd)

    suggestions: list[dict] = []

    if profile_source == "inferred" or not profile_path.exists() or not context_path.exists():
        suggestions.append(
            {
                "command": "skillsmith init --guided",
                "why": "project profile or generated context is missing, so guided init is the fastest path to a usable baseline",
                "evidence": [
                    f"profile={_state_label(profile_path.exists())}",
                    f"context={_state_label(context_path.exists())}",
                    f"profile_source={profile_source}",
                ],
                "priority": 100,
            }
        )

    if drift["has_drift"]:
        suggestions.append(
            {
                "command": "skillsmith sync",
                "why": "derived instructions or context have drifted from the saved profile and should be refreshed together",
                "evidence": [
                    f"missing={', '.join(drift['missing']) or 'none'}",
                    f"drifted={', '.join(drift['drifted']) or 'none'}",
                ],
                "priority": 90,
            }
        )

    if not lockfile["present"] or lockfile["skill_count"] == 0:
        suggestions.append(
            {
                "command": "skillsmith recommend",
                "why": "there is no recorded skill set yet, so the catalog preview is the next useful step before installing anything",
                "evidence": [
                    f"lockfile={_state_label(lockfile['present'])}",
                    f"installed_skills={lockfile['skill_count']}",
                ],
                "priority": 80,
            }
        )
    elif lockfile["signature_state"] not in {"skipped", "valid"} or not lockfile["signature_valid"]:
        suggestions.append(
            {
                "command": "skillsmith audit --strict",
                "why": "the lockfile signature is not healthy, so integrity checks should run before further work",
                "evidence": [lockfile["signature_message"]],
                "priority": 85,
            }
        )

    if git_status.get("available") and git_status.get("dirty"):
        suggestions.append(
            {
                "command": "skillsmith audit --strict",
                "why": "the git worktree has uncommitted changes, so a strict audit is the safest next verification step",
                "evidence": [
                    f"dirty_files={git_status['dirty_count']}",
                    f"untracked={git_status['untracked_count']}",
                ],
                "priority": 70,
            }
        )

    if profile_path.exists() and context_path.exists() and not drift["has_drift"] and lockfile["skill_count"] > 0:
        suggestions.append(
            {
                "command": 'skillsmith compose "build the next feature"',
                "why": "the project instructions, context, and installed skills are in place, so a workflow run is the most useful forward action",
                "evidence": [
                    f"workflows={workflows['count']}",
                    f"git={'clean' if git_status.get('clean') else 'dirty or unavailable'}",
                ],
                "priority": 60,
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "command": "skillsmith report",
                "why": "there is not enough state to recommend a more specific action, so a status summary is the safest default",
                "evidence": ["fallback"],
                "priority": 10,
            }
        )

    suggestions.sort(key=lambda item: (-int(item["priority"]), item["command"]))

    unique: list[dict] = []
    seen: set[str] = set()
    for item in suggestions:
        if item["command"] in seen:
            continue
        seen.add(item["command"])
        unique.append(item)
        if len(unique) >= 3:
            break

    summary = {
        "profile_source": profile_source,
        "git": git_status,
        "drift": drift,
        "lockfile": lockfile,
        "workflows": workflows,
        "profile": profile,
    }
    return unique, summary


def _state_label(present: bool) -> str:
    return "present" if present else "missing"


def _print_summary(summary: dict) -> None:
    table = Table(title="Current Signals", box=None)
    table.add_column("Signal", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Profile source", summary["profile_source"])
    table.add_row("Git", "dirty" if summary["git"].get("dirty") else ("clean" if summary["git"].get("available") else "unavailable"))
    table.add_row("Drift", "yes" if summary["drift"].get("has_drift") else "no")
    table.add_row("Lockfile", f"{summary['lockfile']['skill_count']} skills" if summary["lockfile"]["present"] else "missing")
    table.add_row("Workflows", str(summary["workflows"]["count"]))
    console.print(table)


def _print_suggestions(suggestions: list[dict]) -> None:
    # Emit a plain-text preview first so outputs stay stable in narrow terminals/tests.
    console.print("[bold]Recommendations[/bold]")
    for index, item in enumerate(suggestions, start=1):
        evidence = "; ".join(item["evidence"])
        console.print(f"{index}. {item['command']}")
        console.print(f"   Why: {item['why']}")
        console.print(f"   Evidence: {evidence}")

    table = Table(title="Next Suggestions")
    table.add_column("#", justify="right", style="yellow", no_wrap=True)
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Why", style="white")
    table.add_column("Evidence", style="dim")
    for index, item in enumerate(suggestions, start=1):
        table.add_row(str(index), item["command"], item["why"], "; ".join(item["evidence"]))
        click.echo(f"{index}. {item['command']} - {item['why']} | evidence: {'; '.join(item['evidence'])}")
    console.print(table)


@click.command()
def suggest_command():
    """Suggest the next best commands or workflows for the current project state."""
    cwd = Path.cwd()
    suggestions, summary = _suggestions(cwd)
    console.print("[bold cyan]Skillsmith Suggestions[/bold cyan]")
    _print_summary(summary)
    _print_suggestions(suggestions)
