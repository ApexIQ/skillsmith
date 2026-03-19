from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import click
from rich.table import Table

from . import console, iter_skill_dirs, sanitize_json
from .doctor import _format_recommendation_summary
from .lockfile import LOCKFILE_NAME, _checksum_for_path, load_lockfile, load_trust_health, verify_lockfile_signature
from .providers import curated_pack_candidates, curated_pack_label, explain_candidate, install_policy_for_profile
from .report import (
    _context_index_freshness_summary,
    _current_profile,
    _eval_policy_summary,
    _format_threshold_summary,
    _profile_query,
    _registry_governance_summary,
    _stringify,
    _print_kv_table,
)
from .rendering import managed_file_map, selected_tools


def _severity_rank(severity: str) -> int:
    return {"ok": 0, "warning": 1, "error": 2}.get(severity, 0)


def _check_rendered_file(path: Path, expected: str, cwd: Path) -> dict:
    rel = path.relative_to(cwd).as_posix()
    if not path.exists():
        return {"section": "rendering", "path": rel, "severity": "error", "message": f"{rel} missing"}
    actual = path.read_text(encoding="utf-8", errors="ignore").strip()
    if actual != expected.strip():
        return {
            "section": "rendering",
            "path": rel,
            "severity": "warning",
            "message": f"{rel} is out of sync with .agent/project_profile.yaml",
        }
    return {"section": "rendering", "path": rel, "severity": "ok", "message": f"{rel} in sync"}


def _workflow_surface_label(path: Path) -> str:
    parts = path.parts
    if ".agent" in parts and "workflows" in parts:
        return "internal"
    if ".claude" in parts and "commands" in parts:
        return "claude"
    if ".windsurf" in parts and "workflows" in parts:
        return "windsurf"
    if ".cursor" in parts and "workflows" in parts:
        return "cursor"
    if ".zencoder" in parts and "workflows" in parts:
        return "zencoder"
    return "other"


def _collect_profile_summary(cwd: Path) -> dict:
    profile, profile_source = _current_profile(cwd)
    query = _profile_query(profile)
    policy = install_policy_for_profile(profile)
    candidates = curated_pack_candidates(profile, limit=3)
    recommendations = []
    for candidate in candidates:
        explanation = explain_candidate(candidate, query, profile)
        recommendations.append(
            {
                "name": candidate.name,
                "source": candidate.source,
                "trust_score": candidate.trust_score,
                "why": explanation["reasons"][:3],
            }
        )
    return {
        "source": profile_source,
        "profile": {
            "idea": profile.get("idea"),
            "stage": profile.get("project_stage"),
            "app_type": profile.get("app_type"),
            "languages": profile.get("languages", []),
            "frameworks": profile.get("frameworks", []),
            "package_manager": profile.get("package_manager"),
            "deployment_target": profile.get("deployment_target"),
            "priorities": profile.get("priorities", []),
            "target_tools": profile.get("target_tools", []),
        },
        "selected_tools": sorted(selected_tools(profile)),
        "policy": {
            "allow_remote_skills": policy["allow_remote_skills"],
            "allowed_sources": sorted(policy["allowed_sources"]),
            "min_remote_trust_score": policy["min_remote_trust_score"],
        },
        "starter_pack_label": curated_pack_label(profile),
        "starter_pack": recommendations,
    }


def _collect_state_checks(cwd: Path) -> list[dict]:
    checks: list[dict] = []
    for fname, desc in {
        "PROJECT.md": "Tech stack & vision",
        "ROADMAP.md": "Strategic milestones",
        "STATE.md": "Current task context",
    }.items():
        path = cwd / ".agent" / fname
        if not path.exists():
            checks.append({"section": "state", "path": path.relative_to(cwd).as_posix(), "severity": "error", "message": f".agent/{fname} missing"})
            continue
        if fname == "STATE.md":
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            if age_hours > 24:
                checks.append({"section": "state", "path": path.relative_to(cwd).as_posix(), "severity": "warning", "message": f".agent/{fname} is stale"})
                continue
        checks.append({"section": "state", "path": path.relative_to(cwd).as_posix(), "severity": "ok", "message": f".agent/{fname} ({desc})"})
    return checks


def _collect_integrity_checks(cwd: Path, profile: dict) -> tuple[list[dict], dict, dict]:
    checks: list[dict] = []
    lockfile_summary = {"present": False, "skills": [], "issues": []}
    trust_health = load_trust_health(cwd, profile)

    path_ok = shutil.which("skillsmith") is not None
    checks.append(
        {
            "section": "environment",
            "path": "PATH",
            "severity": "ok" if path_ok else "error",
            "message": "'skillsmith' command is on PATH" if path_ok else "'skillsmith' command is NOT on PATH",
        }
    )

    for path, label in [
        (cwd / "AGENTS.md", "AGENTS.md"),
        (cwd / ".agent" / "project_profile.yaml", ".agent/project_profile.yaml"),
        (cwd / ".agent" / "context" / "project-context.md", ".agent/context/project-context.md"),
    ]:
        if path.exists():
            checks.append({"section": "core", "path": path.relative_to(cwd).as_posix(), "severity": "ok", "message": f"{label} present"})
        else:
            checks.append({"section": "core", "path": path.relative_to(cwd).as_posix(), "severity": "error", "message": f"{label} missing"})

    expected_files = {}
    if (cwd / ".agent" / "project_profile.yaml").exists():
        try:
            expected_files = managed_file_map(cwd, profile)
        except Exception as exc:
            checks.append(
                {
                    "section": "rendering",
                    "path": ".agent/project_profile.yaml",
                    "severity": "error",
                    "message": f"Failed to load project profile: {exc}",
                }
            )

    if expected_files:
        rendered_files = [
            path
            for path in expected_files
            if "workflows" not in path.parts and not (".claude" in path.parts and "commands" in path.parts)
        ]
        for path in sorted(rendered_files):
            checks.append(_check_rendered_file(path, expected_files[path], cwd))

        workflow_files = {
            path: expected for path, expected in expected_files.items() if "workflows" in path.parts or (".claude" in path.parts and "commands" in path.parts)
        }
        for surface in sorted({_workflow_surface_label(path) for path in workflow_files}):
            surface_paths = sorted(path for path in workflow_files if _workflow_surface_label(path) == surface)
            for path in surface_paths:
                checks.append(_check_rendered_file(path, expected_files[path], cwd))
    else:
        checks.append(
            {
                "section": "rendering",
                "path": ".agent/project_profile.yaml",
                "severity": "warning",
                "message": "No expected outputs available; run skillsmith init first",
            }
        )

    skills_dir = cwd / ".agent" / "skills"
    if skills_dir.exists():
        checks.append(
            {
                "section": "skills",
                "path": ".agent/skills",
                "severity": "ok",
                "message": f"{sum(1 for _ in iter_skill_dirs(skills_dir))} skills installed",
            }
        )
    else:
        checks.append({"section": "skills", "path": ".agent/skills", "severity": "warning", "message": ".agent/skills/ not found"})

    lockfile_path = cwd / LOCKFILE_NAME
    if lockfile_path.exists():
        lockfile_summary["present"] = True
        try:
            payload = load_lockfile(cwd)
            signature_status = verify_lockfile_signature(payload)
            if signature_status["state"] != "skipped":
                checks.append(
                    {
                        "section": "lockfile",
                        "path": LOCKFILE_NAME,
                        "severity": "ok" if signature_status["valid"] else "error",
                        "message": signature_status["message"],
                    }
                )
                lockfile_summary["signature"] = signature_status
            skills = sorted(payload.get("skills", []), key=lambda item: (str(item.get("name", "")), str(item.get("source", ""))))
            lockfile_summary["skills"] = []
            policy = install_policy_for_profile(profile)
            for item in skills:
                source = str(item.get("source", "unknown"))
                name = str(item.get("name", "unknown"))
                install_ref = str(item.get("install_ref", ""))
                path_value = str(item.get("path", ""))
                checksum = str(item.get("checksum", ""))
                trust_score = int(item.get("trust_score", 0))
                status = "ok"
                messages: list[str] = []
                install_path = cwd / path_value if path_value else None
                if source != "local" and not install_ref:
                    status = "error"
                    messages.append("missing provenance")
                if not path_value or install_path is None or not install_path.exists():
                    status = "error"
                    messages.append("missing install path")
                if not checksum:
                    status = "error"
                    messages.append("missing checksum")
                elif source == "local" and install_path is not None:
                    actual_checksum = _checksum_for_path(install_path)
                    if not actual_checksum:
                        status = "error"
                        messages.append("missing SKILL.md for checksum verification")
                    elif actual_checksum != checksum:
                        status = "error"
                        messages.append("checksum mismatch")
                if source != "local":
                    if not policy["allow_remote_skills"]:
                        status = "warning" if status == "ok" else status
                        messages.append("remote skills disabled by profile")
                    elif source.lower() not in policy["allowed_sources"]:
                        status = "error"
                        messages.append("source not trusted by profile")
                    elif trust_score < policy["min_remote_trust_score"]:
                        status = "error"
                        messages.append("trust score below minimum")
                rationale = _format_recommendation_summary(item.get("recommendation", {}))
                lockfile_summary["skills"].append(
                    {
                        "name": name,
                        "source": source,
                        "trust_score": trust_score,
                        "path": path_value,
                        "status": status,
                        "issues": messages,
                        "rationale": rationale,
                    }
                )
                severity = status if messages else "ok"
                checks.append(
                    {
                        "section": "lockfile",
                        "path": path_value or name,
                        "severity": severity,
                        "message": f"{name} ({source})" if not messages else f"{name} ({source}): {', '.join(messages)}",
                    }
                )
        except Exception as exc:
            checks.append({"section": "lockfile", "path": LOCKFILE_NAME, "severity": "error", "message": f"Failed to read {LOCKFILE_NAME}: {exc}"})
    else:
        checks.append({"section": "lockfile", "path": LOCKFILE_NAME, "severity": "warning", "message": f"{LOCKFILE_NAME} not found"})

    revocations = trust_health["revocations"]
    transparency_log = trust_health["transparency_log"]
    checks.append(
        {
            "section": "trust",
            "path": revocations["path"],
            "severity": "error" if not revocations["valid"] else ("warning" if revocations.get("revoked_trusted_key_ids") else "ok"),
            "message": (
                f"{revocations['path']} present ({revocations['revoked_key_count']} revoked keys)"
                if revocations["present"]
                else f"{revocations['path']} not found"
            )
            if revocations["valid"]
            else f"{revocations['path']} invalid: {', '.join(revocations['issues'])}",
        }
    )
    checks.append(
        {
            "section": "trust",
            "path": transparency_log["path"],
            "severity": "error" if not transparency_log["valid"] else ("warning" if transparency_log["malformed_count"] else "ok"),
            "message": (
                f"{transparency_log['path']} present ({transparency_log['entry_count']} entries, {transparency_log['malformed_count']} malformed)"
                if transparency_log["present"]
                else f"{transparency_log['path']} not found"
            )
            if transparency_log["valid"]
            else f"{transparency_log['path']} invalid: {', '.join(transparency_log['issues'])}",
        }
    )

    return checks, lockfile_summary, trust_health


def _build_audit(cwd: Path) -> dict:
    profile, profile_source = _current_profile(cwd)
    profile_summary = _collect_profile_summary(cwd)
    eval_policy = _eval_policy_summary(cwd, profile)
    context_index_freshness = _context_index_freshness_summary(cwd)
    registry_governance = _registry_governance_summary(cwd)
    integrity_checks, lockfile_summary, trust_health = _collect_integrity_checks(cwd, profile)
    state_checks = _collect_state_checks(cwd)
    all_checks = integrity_checks + state_checks
    warning_count = sum(1 for check in all_checks if check["severity"] == "warning")
    error_count = sum(1 for check in all_checks if check["severity"] == "error")
    return {
        "profile_source": profile_source,
        "profile_summary": profile_summary,
        "eval_policy": eval_policy,
        "context_index_freshness": context_index_freshness,
        "registry_governance": registry_governance,
        "provider_reliability": _provider_reliability(cwd),
        "checks": all_checks,
        "lockfile": lockfile_summary,
        "trust_health": trust_health,
        "summary": {
            "warnings": warning_count,
            "errors": error_count,
            "ok": warning_count == 0 and error_count == 0,
        },
    }


def _provider_reliability(cwd: Path) -> list[dict]:
    path = cwd / ".agent" / "evals" / "provider_telemetry.jsonl"
    if not path.exists():
        return []
    per_provider: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        provider = str(payload.get("provider", "unknown"))
        status = str(payload.get("status", "error"))
        bucket = per_provider.setdefault(provider, {"ok": 0, "total": 0})
        bucket["total"] += 1
        if status == "ok":
            bucket["ok"] += 1
    summary = []
    for provider, stats in sorted(per_provider.items()):
        total = max(1, stats["total"])
        summary.append(
            {
                "provider": provider,
                "samples": stats["total"],
                "success_rate": round((stats["ok"] / total) * 100, 2),
            }
        )
    return summary


def _format_history_event(entry: dict) -> str:
    if not isinstance(entry, dict):
        return "unknown"
    parts = [
        str(entry.get("name", "unknown")),
        str(entry.get("action", "unknown")),
        str(entry.get("at", "unknown time")),
    ]
    actor = str(entry.get("actor", "")).strip()
    if actor:
        parts.append(actor)
    from_state = str(entry.get("from_state", "")).strip()
    to_state = str(entry.get("to_state", "")).strip()
    if from_state and to_state:
        parts.append(f"{from_state}->{to_state}")
    elif from_state or to_state:
        parts.append(from_state or to_state)
    return " / ".join(parts)


def _render_human(result: dict) -> None:
    profile_summary = result["profile_summary"]
    console.print("[bold cyan]Skillsmith Audit[/bold cyan]")
    console.print(
        f"[dim]Profile source: {result['profile_source']} | selected tools: {_stringify(profile_summary['selected_tools'])} | warnings: {result['summary']['warnings']} | errors: {result['summary']['errors']}[/dim]"
    )

    table = Table(title="Profile", show_header=False, box=None, pad_edge=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in [
        ("Idea", _stringify(profile_summary["profile"].get("idea"))),
        ("Stage", _stringify(profile_summary["profile"].get("stage"))),
        ("App type", _stringify(profile_summary["profile"].get("app_type"))),
        ("Languages", _stringify(profile_summary["profile"].get("languages"))),
        ("Frameworks", _stringify(profile_summary["profile"].get("frameworks"))),
        ("Package manager", _stringify(profile_summary["profile"].get("package_manager"))),
        ("Deployment target", _stringify(profile_summary["profile"].get("deployment_target"))),
        ("Priorities", _stringify(profile_summary["profile"].get("priorities"))),
        ("Target tools", _stringify(profile_summary["profile"].get("target_tools"))),
    ]:
        table.add_row(key, value)
    console.print(table)

    console.print(f"\n[bold]Starter Pack ({profile_summary['starter_pack_label']})[/bold]")
    if profile_summary["starter_pack"]:
        starter_pack_table = Table(box=None)
        starter_pack_table.add_column("Skill", style="cyan")
        starter_pack_table.add_column("Source", style="green")
        starter_pack_table.add_column("Why", style="yellow")
        for candidate in profile_summary["starter_pack"]:
            starter_pack_table.add_row(candidate["name"], candidate["source"], "; ".join(candidate["why"]))
        console.print(starter_pack_table)
    else:
        console.print("  [dim]-[/dim] no starter-pack candidates available from the catalog")

    eval_policy = result["eval_policy"]
    _print_kv_table(
        "Eval Policy",
        [
            ("Selected budget profile", _stringify(eval_policy["selected_budget_profile"])),
            ("Budget selector", _stringify(eval_policy["selected_budget_profile_selector"])),
            ("Selected pack", _stringify(eval_policy["selected_budget_profile_pack"])),
            ("Thresholds used", _format_threshold_summary(eval_policy["effective_thresholds"])),
            ("CI enforcement", eval_policy["ci_enforcement_state"]),
            ("CI opt-out", "enabled" if eval_policy["ci_opt_out"] else "disabled"),
            ("Gate enabled", "enabled" if eval_policy["gate_enabled"] else "disabled"),
        ],
    )

    context_index = result["context_index_freshness"]
    _print_kv_table(
        "Context Index Freshness",
        [
            ("File count", str(context_index["file_count"])),
            ("Average freshness", str(context_index["average_freshness_score"])),
            ("Stale threshold", str(context_index["stale_threshold"])),
            ("Stale files", str(context_index["stale_count"])),
            ("Stale paths", _stringify(context_index["stale_files"])),
        ],
    )

    registry_governance = result["registry_governance"]
    _print_kv_table(
        "Registry Governance",
        [
            ("Entries", str(registry_governance["entry_count"])),
            ("Approval pending", str(registry_governance["approval_pending_count"])),
            ("Deprecated", str(registry_governance["deprecated_count"])),
            ("Recent history events", _stringify([_format_history_event(event) for event in registry_governance["recent_history_events"]])),
        ],
    )

    trust_health = result["trust_health"]
    revocations = trust_health["revocations"]
    transparency_log = trust_health["transparency_log"]
    console.print("\n[bold]Trust Health[/bold]")
    trust_table = Table(box=None)
    trust_table.add_column("Signal", style="cyan")
    trust_table.add_column("Status", style="white")
    trust_table.add_column("Details", style="yellow")
    trust_table.add_row(
        "Revocation file",
        "present" if revocations["present"] else "not found",
        _stringify(revocations["revoked_key_ids"]) if revocations["revoked_key_ids"] else "none",
    )
    trust_table.add_row(
        "Revoked trusted keys",
        "present" if revocations.get("revoked_trusted_key_ids") else "none",
        _stringify(revocations.get("revoked_trusted_key_ids", [])) if revocations.get("revoked_trusted_key_ids") else "none",
    )
    trust_table.add_row(
        "Transparency log",
        "present" if transparency_log["present"] else "not found",
        f"{transparency_log['entry_count']} entries, {transparency_log['malformed_count']} malformed",
    )
    trust_table.add_row(
        "Latest log entry",
        "available" if transparency_log.get("latest_entry") else "none",
        _stringify(transparency_log.get("latest_entry")) if transparency_log.get("latest_entry") else "none",
    )
    console.print(trust_table)

    grouped: dict[str, list[dict]] = {}
    for check in result["checks"]:
        if check["severity"] == "ok":
            continue
        grouped.setdefault(check["section"], []).append(check)

    for section in ["environment", "core", "rendering", "skills", "lockfile", "trust", "state"]:
        items = grouped.get(section, [])
        title = {
            "environment": "Executable PATH",
            "core": "Core Files",
            "rendering": "Rendered Outputs",
            "skills": "Skills",
            "lockfile": "Lockfile",
            "trust": "Trust",
            "state": "State Files",
        }[section]
        console.print(f"\n[bold]{title}[/bold]")
        if not items:
            console.print("  [green][OK][/green] no issues")
            continue
        for item in sorted(items, key=lambda entry: entry["path"]):
            marker = "[red][!!][/red]" if item["severity"] == "error" else "[yellow][!!][/yellow]"
            console.print(f"  {marker} {item['message']}")

    if result["lockfile"]["present"] and result["lockfile"]["skills"]:
        console.print("\n[bold]Lockfile Summary[/bold]")
        for item in result["lockfile"]["skills"]:
            if item["rationale"] == "no recorded rationale":
                continue
            console.print(f"  [cyan][INFO][/cyan] {item['name']}: {item['rationale']}")

    if result["summary"]["ok"]:
        console.print("\n[bold green][OK] Audit passed.[/bold green]")
    else:
        console.print("\n[bold yellow][!!] Issues found. Run `skillsmith align` or `skillsmith doctor` to repair generated files.[/bold yellow]")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable audit results")
@click.option("--strict", is_flag=True, help="Exit non-zero when any warning or error is detected")
def audit_command(as_json: bool, strict: bool):
    """Run a compact report-plus-health audit for the current project."""
    cwd = Path.cwd()
    result = sanitize_json(_build_audit(cwd))
    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        _render_human(result)
    if strict and not result["summary"]["ok"]:
        raise click.exceptions.Exit(1)
