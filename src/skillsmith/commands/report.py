from __future__ import annotations

from pathlib import Path
import json

import click
from rich.table import Table

from . import console, sanitize_json
from .doctor import _format_recommendation_summary, _report_render_group
from .init import _infer_project_profile
from .lockfile import LOCKFILE_NAME, load_lockfile, load_trust_health, verify_lockfile_signature
from .registry import _load_registry
from .providers import curated_pack_candidates, curated_pack_label, explain_candidate, install_policy_for_profile
from .rendering import load_project_profile, managed_file_map, selected_tools


def _stringify(value) -> str:
    if isinstance(value, (list, tuple, set)):
        items = [str(item) for item in value if item not in (None, "")]
        return ", ".join(items) if items else "none"
    if value in (None, ""):
        return "not-specified"
    return str(value)


def _current_profile(cwd: Path) -> tuple[dict, str]:
    try:
        profile = load_project_profile(cwd)
        if isinstance(profile, dict) and profile:
            return profile, "saved"
    except Exception:
        pass
    return _infer_project_profile(cwd), "inferred"


def _profile_query(profile: dict) -> str:
    parts: list[str] = []
    for field in ["app_type", "languages", "frameworks", "priorities", "target_tools", "build_commands", "test_commands"]:
        value = profile.get(field)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if item and item != "unknown")
        elif value and value != "unknown":
            parts.append(str(value))
    return " ".join(parts) or str(profile.get("app_type", "project"))


def _tool_snapshot_paths(cwd: Path, profile: dict) -> list[Path]:
    paths = [
        cwd / "AGENTS.md",
        cwd / ".agent" / "PROJECT.md",
        cwd / ".agent" / "ROADMAP.md",
        cwd / ".agent" / "STATE.md",
    ]
    tool_paths = {
        "claude": cwd / "CLAUDE.md",
        "gemini": cwd / "GEMINI.md",
        "cursor": cwd / ".cursor" / "rules" / "skillsmith.mdc",
        "windsurf": cwd / ".windsurf" / "rules" / "skillsmith.md",
        "zencoder": cwd / ".zencoder" / "rules" / "skillsmith.md",
        "copilot": cwd / ".github" / "copilot-instructions.md",
        "github-copilot": cwd / ".github" / "copilot-instructions.md",
    }
    for tool in sorted(selected_tools(profile)):
        path = tool_paths.get(tool)
        if path is not None:
            paths.append(path)
    return paths


def _print_kv_table(title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(title=title, show_header=False, box=None, pad_edge=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


def _provider_reliability(cwd: Path) -> list[tuple[str, str, str]]:
    path = cwd / ".agent" / "evals" / "provider_telemetry.jsonl"
    if not path.exists():
        return []
    per_provider: dict[str, dict[str, int]] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            item = json.loads(raw_line)
        except Exception:
            continue
        provider = str(item.get("provider", "unknown"))
        status = str(item.get("status", "error"))
        bucket = per_provider.setdefault(provider, {"ok": 0, "total": 0})
        bucket["total"] += 1
        if status == "ok":
            bucket["ok"] += 1
    rows = []
    for provider, stats in sorted(per_provider.items()):
        total = max(1, stats["total"])
        success_rate = round((stats["ok"] / total) * 100, 2)
        rows.append((provider, f"{success_rate}%", str(stats["total"])))
    return rows


def _format_threshold_summary(thresholds: dict[str, object]) -> str:
    return ", ".join(
        f"{key}={_stringify(thresholds.get(key))}"
        for key in ["min_tacr_delta", "max_latency_increase_ms", "max_cost_increase_usd"]
    )


def _eval_policy_summary(cwd: Path, profile: dict) -> dict:
    from .eval_cmd import _resolve_eval_policy

    resolution = _resolve_eval_policy(
        cwd,
        pack=None,
        min_tacr_delta=None,
        max_latency_increase_ms=None,
        max_cost_increase_usd=None,
        no_ci_policy=False,
    )
    policy = resolution["policy"]
    return {
        "source": policy.get("source", ""),
        "app_type": policy.get("app_type", profile.get("app_type", "project")),
        "selected_budget_profile": policy.get("selected_budget_profile"),
        "selected_budget_profile_selector": policy.get("selected_budget_profile_selector"),
        "selected_budget_profile_pack": policy.get("selected_budget_profile_pack"),
        "selected_budget_profile_thresholds": policy.get("selected_budget_profile_thresholds", {}),
        "effective_pack": resolution.get("pack"),
        "effective_thresholds": resolution.get("thresholds", {}),
        "gate_enabled": bool(resolution.get("gate_enabled")),
        "ci_enforced": bool(policy.get("ci_enforced")),
        "ci_enforcement_state": "enabled" if policy.get("ci_enforced") else "disabled",
        "ci_opt_out": bool(policy.get("opt_out")),
    }


def _context_index_freshness_summary(cwd: Path) -> dict:
    path = cwd / ".agent" / "context" / "index.json"
    if not path.exists():
        return {
            "present": False,
            "path": path.relative_to(cwd).as_posix(),
            "valid": False,
            "file_count": 0,
            "average_freshness_score": 0.0,
            "stale_threshold": 50,
            "stale_count": 0,
            "stale_files": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "present": True,
            "path": path.relative_to(cwd).as_posix(),
            "valid": False,
            "issues": [str(exc)],
            "file_count": 0,
            "average_freshness_score": 0.0,
            "stale_threshold": 50,
            "stale_count": 0,
            "stale_files": [],
        }
    files = payload.get("files", []) if isinstance(payload, dict) else []
    file_count = payload.get("file_count", len(files)) if isinstance(payload, dict) else len(files)
    scores: list[int] = []
    stale_files: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        score = int(item.get("freshness_score", 0) or 0)
        scores.append(score)
        if score < 50:
            stale_files.append(str(item.get("path", "unknown")))
    average_freshness = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {
        "present": True,
        "path": path.relative_to(cwd).as_posix(),
        "valid": True,
        "file_count": int(file_count),
        "average_freshness_score": average_freshness,
        "stale_threshold": 50,
        "stale_count": len(stale_files),
        "stale_files": stale_files[:5],
    }


def _registry_governance_summary(cwd: Path) -> dict:
    path = cwd / ".agent" / "registry" / "skills.json"
    payload = _load_registry(cwd)
    skills = payload.get("skills", []) if isinstance(payload, dict) else []
    recent_events: list[dict] = []
    for entry in skills:
        if not isinstance(entry, dict):
            continue
        entry_name = str(entry.get("name", "unknown"))
        for event in entry.get("change_history", []):
            if not isinstance(event, dict):
                continue
            recent_events.append(
                {
                    "name": entry_name,
                    "action": str(event.get("action", "")),
                    "actor": str(event.get("actor", "")),
                    "at": str(event.get("at", "")),
                    "from_state": str(event.get("from_state", "")),
                    "to_state": str(event.get("to_state", "")),
                    "approval_status": str(event.get("approval_status", "")),
                    "note": str(event.get("note", "")) if event.get("note") is not None else "",
                }
            )
    recent_events.sort(key=lambda item: (item["at"], item["name"], item["action"]), reverse=True)
    approval_pending_count = sum(
        1 for entry in skills if isinstance(entry, dict) and str(entry.get("approval_status", "")).lower() == "pending"
    )
    deprecated_count = sum(
        1 for entry in skills if isinstance(entry, dict) and str(entry.get("lifecycle_state", "")).lower() == "deprecated"
    )
    return {
        "present": path.exists(),
        "path": path.relative_to(cwd).as_posix(),
        "entry_count": len([entry for entry in skills if isinstance(entry, dict)]),
        "approval_pending_count": approval_pending_count,
        "deprecated_count": deprecated_count,
        "recent_history_events": recent_events[:5],
    }


def _build_report(cwd: Path) -> dict:
    profile, profile_source = _current_profile(cwd)
    query = _profile_query(profile)
    policy = install_policy_for_profile(profile)
    policy_summary = {
        "allow_remote_skills": bool(policy["allow_remote_skills"]),
        "allowed_sources": sorted(policy["allowed_sources"]),
        "allowed_remote_domains": sorted(policy.get("allowed_remote_domains", [])),
        "publisher_verification_mode": policy.get("publisher_verification_mode"),
        "publisher_signature_scheme_mode": policy.get("publisher_signature_scheme_mode"),
        "publisher_signature_algorithms": list(policy.get("publisher_signature_algorithms", [])),
        "trusted_publisher_key_ids": sorted(policy.get("trusted_publisher_key_ids", [])),
        "trusted_publisher_public_key_ids": sorted(policy.get("trusted_publisher_public_key_ids", [])),
        "publisher_key_rotation": policy.get("publisher_key_rotation", {}),
        "min_remote_trust_score": policy.get("min_remote_trust_score"),
    }
    trust_health = load_trust_health(cwd, profile)
    expected_files = managed_file_map(cwd, profile)
    snapshot_files = {
        path: expected_files[path]
        for path in _tool_snapshot_paths(cwd, profile)
        if path in expected_files
    }
    return {
        "profile_source": profile_source,
        "profile": profile,
        "query": query,
        "starter_pack_label": curated_pack_label(profile),
        "starter_pack": [
            {
                "name": candidate.name,
                "source": candidate.source,
                "why": explain_candidate(candidate, query, profile)["reasons"][:3],
            }
            for candidate in curated_pack_candidates(profile, limit=5)
        ],
        "policy": policy_summary,
        "trust_health": trust_health,
        "provider_reliability": _provider_reliability(cwd),
        "eval_policy": _eval_policy_summary(cwd, profile),
        "context_index_freshness": _context_index_freshness_summary(cwd),
        "registry_governance": _registry_governance_summary(cwd),
        "snapshot_files": {path.relative_to(cwd).as_posix(): expected_files[path] for path in snapshot_files},
    }


def _format_log_entry(entry: dict | None) -> str:
    if not isinstance(entry, dict):
        return "none"
    parts = [
        str(entry.get("logged_at", "")).strip() or "unknown time",
        str(entry.get("state", "")).strip() or "unknown state",
    ]
    key_id = str(entry.get("key_id", "")).strip()
    if key_id:
        parts.append(key_id)
    return " / ".join(parts)


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable report results")
def report_command(as_json: bool):
    """Summarize the current profile, installs, trust policy, and drift."""
    cwd = Path.cwd()
    result = sanitize_json(_build_report(cwd))

    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
        return

    profile = result["profile"]
    profile_source = result["profile_source"]
    policy = result["policy"]
    trust_health = result["trust_health"]
    snapshot_files = {
        cwd / rel_path: content for rel_path, content in result["snapshot_files"].items()
    }

    console.print("[bold cyan]Skillsmith Report[/bold cyan]")
    console.print(
        f"[dim]Profile source: {profile_source} | selected tools: {_stringify(sorted(selected_tools(profile)))}[/dim]"
    )

    _print_kv_table(
        "Profile",
        [
            ("Idea", _stringify(profile.get("idea"))),
            ("Stage", _stringify(profile.get("project_stage"))),
            ("App type", _stringify(profile.get("app_type"))),
            ("Languages", _stringify(profile.get("languages"))),
            ("Frameworks", _stringify(profile.get("frameworks"))),
            ("Package manager", _stringify(profile.get("package_manager"))),
            ("Deployment target", _stringify(profile.get("deployment_target"))),
            ("Priorities", _stringify(profile.get("priorities"))),
            ("Target tools", _stringify(profile.get("target_tools"))),
        ],
    )

    console.print(f"\n[bold]Selected Starter Pack ({result['starter_pack_label']})[/bold]")
    if result["starter_pack"]:
        starter_pack_table = Table(box=None)
        starter_pack_table.add_column("Skill", style="cyan")
        starter_pack_table.add_column("Source", style="green")
        starter_pack_table.add_column("Why", style="yellow")
        for candidate in result["starter_pack"]:
            starter_pack_table.add_row(candidate["name"], candidate["source"], "; ".join(candidate["why"]))
        console.print(starter_pack_table)
    else:
        console.print("  [dim]-[/dim] no starter-pack candidates available from the catalog")

    console.print(f"\n[bold]Installed Skills ({LOCKFILE_NAME})[/bold]")
    lockfile_path = cwd / LOCKFILE_NAME
    if not lockfile_path.exists():
        console.print(f"  [dim]-[/dim] {LOCKFILE_NAME} not found")
    else:
        try:
            payload = load_lockfile(cwd)
            signature_status = verify_lockfile_signature(payload)
            if signature_status["state"] != "skipped":
                marker = "[green][OK][/green]" if signature_status["valid"] else "[yellow][!!][/yellow]"
                console.print(f"  {marker} {signature_status['message']}")
            skills = sorted(payload.get("skills", []), key=lambda item: str(item.get("name", "")))
            if not skills:
                console.print(f"  [dim]-[/dim] no recorded installs in {LOCKFILE_NAME}")
            else:
                skills_table = Table(box=None)
                skills_table.add_column("Skill", style="cyan")
                skills_table.add_column("Source", style="green")
                skills_table.add_column("Trust", justify="right")
                skills_table.add_column("Recommendation rationale", style="yellow")
                skills_table.add_column("Path", style="dim")
                for item in skills:
                    skills_table.add_row(
                        str(item.get("name", "unknown")),
                        str(item.get("source", "unknown")),
                        str(item.get("trust_score", 0)),
                        _format_recommendation_summary(item.get("recommendation", {})),
                        str(item.get("path", "")),
                    )
                console.print(skills_table)
        except Exception as exc:
            console.print(f"  [red][!!][/red] Failed to read {LOCKFILE_NAME}: {exc}")

    _print_kv_table(
        "Remote Policy",
        [
            ("Allow remote skills", "enabled" if policy["allow_remote_skills"] else "disabled"),
            ("Trusted sources", _stringify(sorted(policy["allowed_sources"]))),
            ("Allowed remote domains", _stringify(sorted(policy.get("allowed_remote_domains", [])))),
            ("Publisher verification mode", _stringify(policy.get("publisher_verification_mode"))),
            ("Signature scheme mode", _stringify(policy.get("publisher_signature_scheme_mode"))),
            ("Allowed signature algorithms", _stringify(policy.get("publisher_signature_algorithms"))),
            ("Trusted HMAC keys", _stringify(sorted(policy.get("trusted_publisher_key_ids", [])))),
            ("Trusted RSA keys", _stringify(sorted(policy.get("trusted_publisher_public_key_ids", [])))),
            ("Publisher key rotation", _stringify(policy.get("publisher_key_rotation"))),
            ("Minimum remote trust", str(policy["min_remote_trust_score"])),
        ],
    )

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
    context_rows = [
        ("File count", str(context_index["file_count"])),
        ("Average freshness", str(context_index["average_freshness_score"])),
        ("Stale threshold", str(context_index["stale_threshold"])),
        ("Stale files", str(context_index["stale_count"])),
        ("Stale paths", _stringify(context_index["stale_files"])),
    ]
    _print_kv_table("Context Index Freshness", context_rows)

    registry_governance = result["registry_governance"]
    registry_rows = [
        ("Entries", str(registry_governance["entry_count"])),
        ("Approval pending", str(registry_governance["approval_pending_count"])),
        ("Deprecated", str(registry_governance["deprecated_count"])),
        (
            "Recent history events",
            _stringify(
                [
                    f"{event['name']}:{event['action']}@{event['at']}"
                    for event in registry_governance["recent_history_events"]
                ]
            ),
        ),
    ]
    _print_kv_table("Registry Governance", registry_rows)

    revocations = trust_health["revocations"]
    transparency_log = trust_health["transparency_log"]
    _print_kv_table(
        "Trust Health",
        [
            ("Revocation file", "present" if revocations["present"] else "not found"),
            ("Revoked keys", _stringify(revocations["revoked_key_ids"])),
            ("Revoked trusted keys", _stringify(revocations.get("revoked_trusted_key_ids", []))),
            ("Revocation health", "ok" if revocations["valid"] else _stringify(revocations["issues"])),
            (
                "Transparency log",
                "present" if transparency_log["present"] else "not found",
            ),
            ("Log entries", str(transparency_log["entry_count"])),
            ("Malformed log lines", str(transparency_log["malformed_count"])),
            ("Latest log entry", _format_log_entry(transparency_log.get("latest_entry"))),
            ("Log health", "ok" if transparency_log["valid"] else _stringify(transparency_log["issues"])),
        ],
    )

    reliability_rows = result["provider_reliability"]
    console.print("\n[bold]Provider Reliability (recent)[/bold]")
    if not reliability_rows:
        console.print("  [dim]-[/dim] no telemetry available")
    else:
        table = Table(box=None)
        table.add_column("Provider", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Samples", justify="right")
        for provider, success_rate, samples in reliability_rows:
            table.add_row(provider, success_rate, samples)
        console.print(table)

    _report_render_group("Quick Drift Snapshot", snapshot_files, cwd)
    console.print("[dim]Use `skillsmith doctor` for the full rendered-file and workflow-surface audit.[/dim]")
