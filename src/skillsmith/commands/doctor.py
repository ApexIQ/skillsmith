import shutil
import sys
import time
import json
from collections import defaultdict
from pathlib import Path

import click

from . import console, iter_skill_dirs
from .lockfile import (
    LOCKFILE_NAME,
    _checksum_for_path,
    load_lockfile,
    lockfile_signing_enabled,
    refresh_local_lockfile_verification_timestamps,
    verify_lockfile_signature,
    write_lockfile,
)
from .providers import install_policy_for_profile
from .rendering import load_project_profile, managed_file_map, selected_tools


def _check_path_status(path: Path, label: str) -> tuple[bool, str]:
    if path.exists():
        return True, f"  [green][OK][/green] {label}"
    return False, f"  [red][!!][/red] {label} missing"


def _check_rendered_file(path: Path, expected: str, cwd: Path) -> tuple[bool, str]:
    rel = path.relative_to(cwd)
    if not path.exists():
        return False, f"  [red][!!][/red] {rel} missing"
    actual = path.read_text(encoding="utf-8", errors="ignore").strip()
    if actual != expected.strip():
        return False, f"  [yellow][!!][/yellow] {rel} is out of sync with .agent/project_profile.yaml"
    return True, f"  [green][OK][/green] {rel}"


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


def _report_render_group(title: str, files: dict[Path, str], cwd: Path) -> bool:
    section_ok = True
    console.print(f"\n[bold]{title}[/bold]")
    if not files:
        console.print("  [dim]-[/dim] none expected for current profile")
        return True
    for path in sorted(files):
        ok, message = _check_rendered_file(path, files[path], cwd)
        console.print(message)
        section_ok &= ok
    return section_ok


def _report_workflow_surfaces(files: dict[Path, str], cwd: Path) -> bool:
    console.print("\n[bold]Workflow Surfaces[/bold]")
    workflow_files = {path: expected for path, expected in files.items() if "workflows" in path.parts or ".claude" in path.parts and "commands" in path.parts}
    if not workflow_files:
        console.print("  [dim]-[/dim] none expected for current profile")
        return True

    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in workflow_files:
        grouped[_workflow_surface_label(path)].append(path)

    section_ok = True
    for label in sorted(grouped):
        console.print(f"  [bold]{label}[/bold]")
        for path in sorted(grouped[label]):
            ok, message = _check_rendered_file(path, files[path], cwd)
            console.print(message)
            section_ok &= ok
    return section_ok


def _readiness_check(name: str, ok: bool, details: str) -> dict:
    return {"name": name, "ok": ok, "details": details}


def _readiness_summary(checks: list[dict]) -> dict:
    total = len(checks)
    passed = sum(1 for item in checks if item["ok"])
    score = 100 if total == 0 else round((passed / total) * 100)
    failing = [item for item in checks if not item["ok"]]
    return {
        "score": int(score),
        "total": total,
        "passed": passed,
        "failing": failing,
    }


def _format_recommendation_summary(recommendation: dict) -> str:
    if not isinstance(recommendation, dict):
        return "no recorded rationale"

    starter_pack = recommendation.get("starter_pack") or recommendation.get("starter_pack_label")
    reasons = recommendation.get("reasons", [])

    parts = []
    if starter_pack:
        parts.append(f"starter pack: {starter_pack}")
    if reasons:
        parts.append("reasons: " + ", ".join(str(reason) for reason in reasons[:3]))
    return " | ".join(parts) if parts else "no recorded rationale"


def _doctor_machine_summary(cwd: Path, *, strict: bool) -> dict:
    missing: list[str] = []
    stale: list[str] = []
    checks: list[dict] = []

    def add_check(name: str, ok: bool, details: str) -> None:
        checks.append({"name": name, "ok": ok, "details": details})
        if not ok and details == "missing":
            missing.append(name)
        if not ok and details == "stale":
            stale.append(name)

    agents_md = cwd / "AGENTS.md"
    profile_path = cwd / ".agent" / "project_profile.yaml"
    context_path = cwd / ".agent" / "context" / "project-context.md"
    state_path = cwd / ".agent" / "STATE.md"

    add_check("AGENTS.md", agents_md.exists(), "present" if agents_md.exists() else "missing")
    add_check(".agent/project_profile.yaml", profile_path.exists(), "present" if profile_path.exists() else "missing")
    add_check(
        ".agent/context/project-context.md",
        context_path.exists(),
        "present" if context_path.exists() else "missing",
    )
    if not state_path.exists():
        add_check(".agent/STATE.md age <=24h", False, "missing")
    else:
        age_hours = (time.time() - state_path.stat().st_mtime) / 3600
        add_check(".agent/STATE.md age <=24h", age_hours <= 24, "present" if age_hours <= 24 else "stale")

    ok = all(item["ok"] for item in checks)
    readiness_checks = [_readiness_check(item["name"], item["ok"], item["details"]) for item in checks]
    readiness = _readiness_summary(readiness_checks)
    return {
        "ok": ok,
        "cwd": str(cwd),
        "checks": checks,
        "missing": missing,
        "stale": stale,
        "readiness_score": readiness["score"],
        "readiness_checklist": readiness_checks,
        "readiness_failing_checks": readiness["failing"],
        "readiness_passing_checks": readiness["passed"],
        "readiness_total_checks": readiness["total"],
        "strict_failed": bool(strict and not ok),
    }


@click.command()
@click.option("--fix", is_flag=True, help="Auto-fix missing platform files by running init")
@click.option("--strict", is_flag=True, help="Exit non-zero when any warning or error is detected")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON summary output")
@click.argument("directory", required=False, type=click.Path(file_okay=False, dir_okay=True, path_type=Path), default=".")
def doctor_command(fix, strict, as_json, directory):
    """Diagnose project alignment and skill health."""
    cwd = directory.resolve()
    if as_json:
        payload = _doctor_machine_summary(cwd, strict=strict)
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if payload["strict_failed"]:
            raise click.exceptions.Exit(1)
        return

    all_ok = True
    fatal_error = False

    console.print("[bold]Executable PATH[/bold]")
    is_on_path = shutil.which("skillsmith") is not None
    if is_on_path:
        console.print("  [green][OK][/green] 'skillsmith' command is on your PATH")
    else:
        all_ok = False
        console.print("  [red][!!][/red] 'skillsmith' is NOT on your PATH")
        import sysconfig

        scripts_dir = sysconfig.get_path("scripts") or str(Path(sys.executable).parent / "Scripts")
        console.print(f"  [dim]Expected location: {scripts_dir}[/dim]")
        if sys.platform == "win32":
            console.print(f"  [yellow]Tip:[/yellow] Run this to fix permanently: [bold]setx PATH \"%PATH%;{scripts_dir}\"[/bold]")
        else:
            console.print(f"  [yellow]Tip:[/yellow] Add this to your shell profile: [bold]export PATH=\"$PATH:{scripts_dir}\"[/bold]")
        console.print("  [blue][INFO][/blue] [bold]Alternative:[/bold] You can always use [bold]python -m skillsmith[/bold]")

    console.print("\n[bold cyan][ DOCTOR ] Skillsmith Doctor[/bold cyan]\n")

    console.print("[bold]Core Files[/bold]")
    agents_md = cwd / "AGENTS.md"
    ok, message = _check_path_status(agents_md, "AGENTS.md")
    console.print(message)
    all_ok &= ok

    console.print("\n[bold]Profile & Context[/bold]")
    profile_path = cwd / ".agent" / "project_profile.yaml"
    context_path = cwd / ".agent" / "context" / "project-context.md"
    for path, label in [
        (profile_path, ".agent/project_profile.yaml"),
        (context_path, ".agent/context/project-context.md"),
    ]:
        ok, message = _check_path_status(path, label)
        console.print(message)
        all_ok &= ok

    profile = {}
    expected_files: dict[Path, str] = {}
    if profile_path.exists():
        try:
            profile = load_project_profile(cwd)
            expected_files = managed_file_map(cwd, profile)
        except Exception as exc:
            all_ok = False
            fatal_error = True
            console.print(f"  [red][!!][/red] Failed to load project profile: {exc}")

    console.print("\n[bold]State Files (.agent/)[/bold]")
    for fname, desc in {
        "PROJECT.md": "Tech stack & vision",
        "ROADMAP.md": "Strategic milestones",
        "STATE.md": "Current task context",
    }.items():
        fpath = cwd / ".agent" / fname
        if fpath.exists():
            age_hours = (time.time() - fpath.stat().st_mtime) / 3600
            if fname == "STATE.md" and age_hours > 24:
                console.print(f"  [yellow][!!][/yellow] .agent/{fname} is stale ({age_hours:.0f}h old)")
                all_ok = False
            else:
                console.print(f"  [green][OK][/green] .agent/{fname} [dim]({desc})[/dim]")
        else:
            console.print(f"  [red][!!][/red] .agent/{fname} missing")
            all_ok = False

    if expected_files:
        non_workflow_files = {
            path: expected
            for path, expected in expected_files.items()
            if "workflows" not in path.parts and not (".claude" in path.parts and "commands" in path.parts)
        }
        all_ok &= _report_render_group("Tool-Native Outputs", non_workflow_files, cwd)
        all_ok &= _report_workflow_surfaces(expected_files, cwd)
    else:
        console.print("\n[bold]Tool-Native Outputs[/bold]")
        console.print("  [yellow][!!][/yellow] No expected outputs available; run [bold]skillsmith init[/bold] first")
        all_ok = False

    console.print("\n[bold]Selected Tools[/bold]")
    if profile:
        console.print(f"  [green][OK][/green] {_tool_list(selected_tools(profile))}")
    else:
        console.print("  [dim]-[/dim] unknown (project profile missing)")

    console.print("\n[bold]Skills[/bold]")
    skills_dir = cwd / ".agent" / "skills"
    if skills_dir.exists():
        valid = sum(1 for _ in iter_skill_dirs(skills_dir))
        console.print(f"  [green][OK][/green] {valid} skills installed")
    else:
        console.print("  [yellow][!!][/yellow] .agent/skills/ not found")

    console.print("\n[bold]Lockfile[/bold]")
    lockfile_path = cwd / LOCKFILE_NAME
    if lockfile_path.exists():
        try:
            payload = load_lockfile(cwd)
            signature_status = verify_lockfile_signature(payload)
            if signature_status["state"] != "skipped":
                marker = "[green][OK][/green]" if signature_status["valid"] else "[yellow][!!][/yellow]"
                console.print(f"  {marker} {signature_status['message']}")
                if not signature_status["valid"]:
                    all_ok = False
            elif lockfile_signing_enabled():
                all_ok = False
                console.print("  [yellow][!!][/yellow] lockfile signature verification could not run")
            refreshed_payload, verification_findings, lockfile_changed = refresh_local_lockfile_verification_timestamps(cwd, payload)
            if lockfile_changed:
                write_lockfile(cwd, refreshed_payload)
            skills = refreshed_payload.get("skills", [])
            console.print(f"  [green][OK][/green] {LOCKFILE_NAME} with {len(skills)} recorded installs")
            policy = install_policy_for_profile(profile)
            rationale_present = False
            rationale_lines = []
            for index, item in enumerate(skills):
                finding = verification_findings[index] if index < len(verification_findings) else {}
                source = item.get("source", "unknown")
                install_ref = item.get("install_ref", "")
                path_value = item.get("path", "")
                checksum = item.get("checksum", "")
                trust_score = int(item.get("trust_score", 0))
                install_path = cwd / path_value if path_value else None
                if source != "local" and not install_ref:
                    all_ok = False
                    console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} is missing provenance")
                if not path_value or install_path is None or not install_path.exists():
                    all_ok = False
                    console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} has a missing install path")
                    continue
                if not checksum:
                    all_ok = False
                    console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} is missing a checksum")
                elif source == "local":
                    actual_checksum = _checksum_for_path(install_path)
                    if not actual_checksum:
                        all_ok = False
                        console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} is missing SKILL.md and cannot be checksum-verified")
                    elif actual_checksum != checksum:
                        all_ok = False
                        console.print(
                            f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} checksum mismatch; installed local skill may be tampered with"
                        )
                if source == "local":
                    state = finding.get("state")
                    if state == "unverified":
                        all_ok = False
                        console.print(
                            f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} checksum verified but verification timestamp was missing; refreshed to {item.get('verification_timestamp')}"
                        )
                    elif state == "stale":
                        all_ok = False
                        previous_timestamp = finding.get("previous_verification_timestamp", "unknown")
                        console.print(
                            f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} verification timestamp was stale ({previous_timestamp}); refreshed to {item.get('verification_timestamp')}"
                        )
                if source != "local":
                    if not policy["allow_remote_skills"]:
                        all_ok = False
                        console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} is remote but allow_remote_skills is disabled")
                    elif source.lower() not in policy["allowed_sources"]:
                        all_ok = False
                        console.print(f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} source '{source}' is not trusted by the current profile")
                    elif trust_score < policy["min_remote_trust_score"]:
                        all_ok = False
                        console.print(
                            f"  [yellow][!!][/yellow] {item.get('name', 'unknown')} trust score {trust_score} is below min_remote_trust_score {policy['min_remote_trust_score']}"
                        )
                recommendation = item.get("recommendation")
                if isinstance(recommendation, dict) and recommendation.get("reasons"):
                    rationale_present = True
                    rationale_lines.append(
                        f"  [cyan][INFO][/cyan] {item.get('name', 'unknown')}: {_format_recommendation_summary(recommendation)}"
                    )
            if rationale_present:
                console.print("  [bold]Recommendation Rationale[/bold]")
                for line in rationale_lines:
                    console.print(line, soft_wrap=True)
                console.print("  [dim]Recommendation rationale is recorded in skills.lock.json[/dim]")
        except Exception as exc:
            all_ok = False
            console.print(f"  [red][!!][/red] Failed to read {LOCKFILE_NAME}: {exc}")
    else:
        console.print(f"  [dim]-[/dim] {LOCKFILE_NAME} not found")

    readiness_checks = [
        _readiness_check("AGENTS.md", agents_md.exists(), "present" if agents_md.exists() else "missing"),
        _readiness_check(
            ".agent/project_profile.yaml",
            profile_path.exists(),
            "present" if profile_path.exists() else "missing",
        ),
        _readiness_check(
            ".agent/context/project-context.md",
            context_path.exists(),
            "present" if context_path.exists() else "missing",
        ),
        _readiness_check(
            ".agent/STATE.md age <=24h",
            cwd.joinpath(".agent", "STATE.md").exists()
            and ((time.time() - cwd.joinpath(".agent", "STATE.md").stat().st_mtime) / 3600) <= 24,
            "present"
            if cwd.joinpath(".agent", "STATE.md").exists()
            and ((time.time() - cwd.joinpath(".agent", "STATE.md").stat().st_mtime) / 3600) <= 24
            else "stale",
        ),
    ]
    readiness = _readiness_summary(readiness_checks)
    console.print("\n[bold]Readiness Checklist[/bold]")
    console.print(
        f"  [bold]{readiness['score']}/100[/bold] from {readiness['passed']} of {readiness['total']} required checks"
    )
    if readiness["failing"]:
        for item in readiness["failing"]:
            console.print(f"  [red][!!][/red] {item['name']} - {item['details']}")
    else:
        console.print("  [green][OK][/green] No failing checklist entries")

    console.print()
    if all_ok:
        console.print("[bold green][OK] All checks passed! Your skillsmith setup is healthy.[/bold green]")
    else:
        console.print("[bold yellow][!!] Some issues found. Run [bold]skillsmith align[/bold] or [bold]skillsmith init[/bold] to repair generated files.[/bold yellow]")
        if fix:
            console.print("\n[cyan]Running skillsmith align to repair generated files...[/cyan]")
            from .align import align_command
            from click.testing import CliRunner

            runner = CliRunner()
            result = runner.invoke(align_command, [])
            console.print(result.output)
    console.print()
    if strict and not all_ok:
        raise click.exceptions.Exit(1)
    if fatal_error:
        raise click.exceptions.Exit(1)


def _tool_list(tools: set[str]) -> str:
    return ", ".join(sorted(tools)) if tools else "none"
