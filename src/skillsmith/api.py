from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

from click.testing import CliRunner

from .commands.init import init_command
from .commands.doctor import _readiness_check, _readiness_summary
from .commands.workflow_engine import build_workflow, load_rolling_eval_feedback
from .commands.context_index import (
    build_context_retrieval_trace,
    persist_context_retrieval_trace,
    retrieve_context_candidates,
)


class InitArtifacts(TypedDict):
    agents_md: bool
    project_profile: bool
    project_context: bool


class InitProjectResult(TypedDict):
    ok: bool
    cwd: str
    command: str
    exit_code: int
    output: str
    artifacts: InitArtifacts


class ComposeWorkflowResult(TypedDict):
    ok: bool
    cwd: str
    goal: str
    workflow: dict
    trace_path: str | None


class DoctorCheck(TypedDict):
    name: str
    ok: bool
    details: str


class DoctorSummaryResult(TypedDict):
    ok: bool
    cwd: str
    checks: list[DoctorCheck]
    missing: list[str]
    stale: list[str]
    strict_failed: bool


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _resolve_cwd(cwd: str | Path, *, create: bool = False) -> Path:
    path = Path(cwd).expanduser()
    path = path.resolve(strict=False)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _artifact_flags(cwd: Path) -> InitArtifacts:
    return {
        "agents_md": (cwd / "AGENTS.md").exists(),
        "project_profile": (cwd / ".agent" / "project_profile.yaml").exists(),
        "project_context": (cwd / ".agent" / "context" / "project-context.md").exists(),
    }


def _state_age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        return (time.time() - path.stat().st_mtime) / 3600
    except OSError:
        return None


def init_project(
    cwd: str | Path,
    *,
    guided: bool = False,
    auto_install: bool = False,
    minimal: bool = False,
) -> dict:
    resolved_cwd = _resolve_cwd(cwd, create=True)
    command_bits = ["skillsmith", "init"]
    if guided:
        command_bits.append("--guided")
    if auto_install:
        command_bits.append("--auto-install")
    if minimal:
        command_bits.append("--minimal")

    runner = CliRunner()
    args = [flag for flag in ("--guided" if guided else None, "--auto-install" if auto_install else None, "--minimal" if minimal else None) if flag]
    with _pushd(resolved_cwd):
        result = runner.invoke(init_command, args)

    artifacts = _artifact_flags(resolved_cwd)
    return {
        "ok": result.exit_code == 0,
        "cwd": str(resolved_cwd),
        "command": " ".join(command_bits),
        "exit_code": result.exit_code,
        "output": result.output,
        "artifacts": artifacts,
    }


def compose_workflow(
    goal: str,
    cwd: str | Path = ".",
    *,
    max_skills: int = 5,
    mode: str = "standard",
    reflection_retries: int = 0,
    feedback: bool = True,
    feedback_window: int | None = None,
) -> dict:
    resolved_cwd = _resolve_cwd(cwd)
    workflow: dict = {}
    trace_path: str | None = None

    try:
        feedback_artifact = load_rolling_eval_feedback(resolved_cwd, feedback_window=feedback_window) if feedback else None
        workflow = build_workflow(
            goal,
            resolved_cwd,
            max_skills=max_skills,
            execution_mode=mode,
            reflection_max_retries=reflection_retries,
            feedback=feedback_artifact,
        )
        candidates = retrieve_context_candidates(resolved_cwd, goal, limit=max_skills, tier="l1")
        cache_hit = bool(candidates and candidates[0].get("cache_hit", False))
        cache_age_seconds = candidates[0].get("cache_age_seconds") if candidates else None
        cache_key = candidates[0].get("cache_key") if candidates else None
        trace = build_context_retrieval_trace(
            resolved_cwd,
            source="compose",
            query=goal,
            goal=goal,
            tier="l1",
            limit=max_skills,
            candidates=candidates,
            selection={
                "selected_skills": list(workflow.get("skills", [])),
                "workflow_steps": len(workflow.get("steps", [])),
                "cache": {
                    "hit": cache_hit,
                    "age_seconds": cache_age_seconds,
                    "key": cache_key,
                },
            },
            metadata={
                "mode": mode,
                "feedback_enabled": bool(feedback),
                "cache": {
                    "hit": cache_hit,
                    "age_seconds": cache_age_seconds,
                    "key": cache_key,
                },
            },
        )
        trace_file = persist_context_retrieval_trace(resolved_cwd, trace)
        trace_path = trace_file.relative_to(resolved_cwd).as_posix()
        workflow["context_trace"] = trace_path
    except Exception:
        return {
            "ok": False,
            "cwd": str(resolved_cwd),
            "goal": goal,
            "workflow": workflow,
            "trace_path": trace_path,
        }

    return {
        "ok": True,
        "cwd": str(resolved_cwd),
        "goal": goal,
        "workflow": workflow,
        "trace_path": trace_path,
    }


def doctor_summary(cwd: str | Path, *, strict: bool = False) -> dict:
    resolved_cwd = _resolve_cwd(cwd)
    checks: list[DoctorCheck] = []
    missing: list[str] = []
    stale: list[str] = []

    def add_check(name: str, ok: bool, details: str) -> None:
        checks.append({"name": name, "ok": ok, "details": details})
        if not ok:
            if details == "missing":
                missing.append(name)
            elif details.startswith("stale"):
                stale.append(name)

    agents_md = resolved_cwd / "AGENTS.md"
    profile_path = resolved_cwd / ".agent" / "project_profile.yaml"
    context_path = resolved_cwd / ".agent" / "context" / "project-context.md"
    state_path = resolved_cwd / ".agent" / "STATE.md"

    add_check("AGENTS.md", agents_md.exists(), "present" if agents_md.exists() else "missing")
    add_check(
        ".agent/project_profile.yaml",
        profile_path.exists(),
        "present" if profile_path.exists() else "missing",
    )
    add_check(
        ".agent/context/project-context.md",
        context_path.exists(),
        "present" if context_path.exists() else "missing",
    )

    state_age = _state_age_hours(state_path)
    if state_age is None:
        add_check(".agent/STATE.md age <=24h", False, "missing")
    elif state_age <= 24:
        add_check(".agent/STATE.md age <=24h", True, f"age={state_age:.1f}h")
    else:
        add_check(".agent/STATE.md age <=24h", False, f"stale age={state_age:.1f}h")

    ok = all(item["ok"] for item in checks)
    readiness_checks = [_readiness_check(item["name"], item["ok"], item["details"]) for item in checks]
    readiness = _readiness_summary(readiness_checks)
    return {
        "ok": ok,
        "cwd": str(resolved_cwd),
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
