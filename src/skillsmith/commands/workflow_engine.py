from __future__ import annotations

import json
from pathlib import Path
import re
import yaml

from . import TEMPLATE_DIR, load_catalog
from .lockfile import load_lockfile
from .providers import SkillCandidate, rank_candidates

EVAL_POLICY_RELATIVE_PATH = ".agent/evals/policy.json"
EVAL_RESULTS_RELATIVE_DIR = ".agent/evals/results"
TEMPLATE_EVAL_POLICY_PATH = TEMPLATE_DIR / EVAL_POLICY_RELATIVE_PATH
WORKFLOW_STAGE_ORDER = ("discover", "plan", "build", "review", "test", "ship", "reflect")


def _tokenize(text: str) -> set[str]:
    return {token for token in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if token}


def _safe_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return default


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json_payload(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_artifact(path: Path) -> dict | None:
    payload = _load_json_payload(path)
    if isinstance(payload, dict):
        return payload
    return None


def _merge_dicts(base: dict | None, override: dict | None) -> dict:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


def _load_merged_eval_policy_payload(cwd: Path) -> dict:
    merged: dict = {}
    if TEMPLATE_EVAL_POLICY_PATH.exists():
        template_payload = _load_json_payload(TEMPLATE_EVAL_POLICY_PATH)
        if isinstance(template_payload, dict):
            merged = template_payload

    local_policy_path = cwd / EVAL_POLICY_RELATIVE_PATH
    if local_policy_path.exists():
        local_payload = _load_json_payload(local_policy_path)
        if isinstance(local_payload, dict):
            merged = _merge_dicts(merged, local_payload)
    return merged


def _compose_feedback_policy(cwd: Path) -> dict:
    from .eval_cmd import _resolve_eval_policy

    payload = _load_merged_eval_policy_payload(cwd)
    compose_payload = payload.get("compose", {}) if isinstance(payload.get("compose"), dict) else {}
    planner_payload = (
        compose_payload.get("planner_editor", {}) if isinstance(compose_payload.get("planner_editor"), dict) else {}
    )
    policy_resolution = _resolve_eval_policy(
        cwd,
        pack=None,
        min_tacr_delta=None,
        max_latency_increase_ms=None,
        max_cost_increase_usd=None,
        no_ci_policy=False,
    )
    policy = dict(policy_resolution.get("policy", {}))
    policy.update(
        {
        "feedback_window": max(1, _coerce_int(compose_payload.get("feedback_window"), 3)),
        "minimum_artifacts": max(1, _coerce_int(compose_payload.get("minimum_artifacts"), 3)),
        "reflection_retry_cap": max(0, _coerce_int(compose_payload.get("reflection_retry_cap"), 3)),
        "verification_pass_floor": max(1, _coerce_int(compose_payload.get("verification_pass_floor"), 1)),
        "verification_pass_cap": max(1, _coerce_int(compose_payload.get("verification_pass_cap"), 4)),
        "tacr_floor": _coerce_float(compose_payload.get("tacr_floor"), 75.0),
        "delta_tacr_floor": _coerce_float(compose_payload.get("delta_tacr_floor"), 0.0),
        "interventions_threshold": max(0, _coerce_int(compose_payload.get("interventions_threshold"), 3)),
        "latency_increase_threshold_ms": _coerce_float(compose_payload.get("latency_increase_threshold_ms"), 0.0),
        "cost_increase_threshold_usd": _coerce_float(compose_payload.get("cost_increase_threshold_usd"), 0.0),
        "planner_editor": {
            "enabled": _coerce_bool(planner_payload.get("enabled"), True),
            "risk_threshold": max(1, _coerce_int(planner_payload.get("risk_threshold"), 2)),
            "tacr_floor": _coerce_float(planner_payload.get("tacr_floor"), 70.0),
            "delta_tacr_floor": _coerce_float(planner_payload.get("delta_tacr_floor"), 0.0),
            "interventions_threshold": max(0, _coerce_int(planner_payload.get("interventions_threshold"), 2)),
        },
        }
    )
    return policy


def _artifact_files(output_dir: Path) -> list[Path]:
    candidates: list[tuple[str, float, str, Path]] = []
    if not output_dir.exists():
        return []
    for path in output_dir.glob("eval-*.json"):
        if not path.is_file():
            continue
        payload = _load_json_payload(path)
        generated_at = ""
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at", "") or "")
        candidates.append((generated_at, path.stat().st_mtime, path.name, path))
    return [item[3] for item in sorted(candidates, key=lambda item: (item[0], item[1], item[2]))]


def load_profile_or_default(cwd: Path) -> dict:
    profile_path = cwd / ".agent" / "project_profile.yaml"
    if not profile_path.exists():
        return {}
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def load_context_summary(cwd: Path) -> str:
    context_path = cwd / ".agent" / "context" / "project-context.md"
    if not context_path.exists():
        return ""
    return context_path.read_text(encoding="utf-8", errors="ignore")


def load_latest_eval_artifact(cwd: Path) -> dict | None:
    artifact_path = cwd / ".agent" / "evals" / "results" / "latest.json"
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def load_rolling_eval_feedback(cwd: Path, feedback_window: int | None = None) -> dict | None:
    policy = _compose_feedback_policy(cwd)
    requested_window = feedback_window if feedback_window is not None else policy["feedback_window"]
    requested_window = max(1, _coerce_int(requested_window, policy["feedback_window"]))
    effective_window = max(requested_window, policy["minimum_artifacts"])

    output_dir = cwd / EVAL_RESULTS_RELATIVE_DIR
    artifacts: list[tuple[Path, dict]] = []
    for artifact_path in _artifact_files(output_dir):
        payload = _load_artifact(artifact_path)
        if isinstance(payload, dict):
            artifacts.append((artifact_path, payload))

    if len(artifacts) < effective_window:
        return None

    recent_artifacts = artifacts[-effective_window:]
    policy = _compose_feedback_policy(cwd)
    latest_policy = recent_artifacts[-1][1].get("policy", {})
    if isinstance(latest_policy, dict):
        policy = _merge_dicts(policy, latest_policy)
    summary_totals = {
        "tacr": 0.0,
        "avg_latency_ms": 0.0,
        "avg_cost_usd": 0.0,
        "total_interventions": 0.0,
    }
    entries: list[dict] = []
    for artifact_path, payload in recent_artifacts:
        summary = payload.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}
        tacr = _coerce_float(summary.get("tacr"))
        latency = _coerce_float(summary.get("avg_latency_ms"))
        cost = _coerce_float(summary.get("avg_cost_usd"))
        interventions = _coerce_float(summary.get("total_interventions"))
        summary_totals["tacr"] += tacr
        summary_totals["avg_latency_ms"] += latency
        summary_totals["avg_cost_usd"] += cost
        summary_totals["total_interventions"] += interventions
        entries.append(
            {
                "artifact": artifact_path.name,
                "generated_at": str(payload.get("generated_at", "")),
                "summary": {
                    "tacr": tacr,
                    "avg_latency_ms": latency,
                    "avg_cost_usd": cost,
                    "total_interventions": interventions,
                },
            }
        )

    artifact_count = len(recent_artifacts)
    rolling_summary = {
        "artifacts": artifact_count,
        "tacr": round(summary_totals["tacr"] / artifact_count, 2),
        "avg_latency_ms": round(summary_totals["avg_latency_ms"] / artifact_count, 2),
        "avg_cost_usd": round(summary_totals["avg_cost_usd"] / artifact_count, 4),
        "total_interventions": round(summary_totals["total_interventions"] / artifact_count, 2),
    }
    first_path, first_payload = recent_artifacts[0]
    last_path, last_payload = recent_artifacts[-1]
    first_summary = first_payload.get("summary", {})
    last_summary = last_payload.get("summary", {})
    if not isinstance(first_summary, dict):
        first_summary = {}
    if not isinstance(last_summary, dict):
        last_summary = {}
    trend = {
        "available": True,
        "baseline_artifact": first_path.name,
        "latest_artifact": last_path.name,
        "baseline_generated_at": first_payload.get("generated_at"),
        "latest_generated_at": last_payload.get("generated_at"),
        "delta_tacr": round(_coerce_float(last_summary.get("tacr")) - _coerce_float(first_summary.get("tacr")), 2),
        "delta_avg_latency_ms": round(
            _coerce_float(last_summary.get("avg_latency_ms")) - _coerce_float(first_summary.get("avg_latency_ms")), 2
        ),
        "delta_avg_cost_usd": round(
            _coerce_float(last_summary.get("avg_cost_usd")) - _coerce_float(first_summary.get("avg_cost_usd")), 4
        ),
    }

    feedback = {
        "source": output_dir.as_posix(),
        "window": effective_window,
        "requested_window": requested_window,
        "artifact_count": artifact_count,
        "artifacts": entries,
        "summary": rolling_summary,
        "trend": trend,
        "policy": policy,
    }
    if _feedback_adjustments(feedback) is None:
        return None
    return feedback


def installed_skill_candidates(cwd: Path) -> list[SkillCandidate]:
    payload = load_lockfile(cwd)
    candidates = []
    for item in payload.get("skills", []):
        candidates.append(
            SkillCandidate(
                name=str(item.get("name", "unknown")),
                description=str(item.get("metadata", {}).get("description", item.get("name", ""))),
                source=str(item.get("source", "unknown")),
                version=str(item.get("version", "0.0.0")),
                category=str(item.get("category", "general")),
                tags=_safe_list(item.get("tags")),
                install_ref=str(item.get("install_ref", "")),
                trust_score=int(item.get("trust_score", 50)),
                metadata=item.get("metadata", {}),
            )
        )
    return candidates


def catalog_skill_candidates() -> list[SkillCandidate]:
    catalog = load_catalog()
    if not catalog:
        return []
    skills = catalog if isinstance(catalog, list) else catalog.get("skills", {}).values()
    return [
        SkillCandidate(
            name=str(item.get("name", "unknown")),
            description=str(item.get("description", "")),
            source="catalog",
            version=str(item.get("version", "0.0.0")),
            category=str(item.get("category", "general")),
            tags=_safe_list(item.get("tags")),
            install_ref=str(item.get("name", "")),
            trust_score=60,
            metadata=item,
        )
        for item in skills
    ]


def select_skills_for_goal(goal: str, cwd: Path, max_skills: int = 5) -> list[SkillCandidate]:
    profile = load_profile_or_default(cwd)
    installed = installed_skill_candidates(cwd)
    if installed:
        ranked_installed = rank_candidates(installed, goal, profile)
        if ranked_installed:
            return ranked_installed[:max_skills]

    return rank_candidates(catalog_skill_candidates(), goal, profile)[:max_skills]


def _goal_kind(goal_tokens: set[str]) -> str:
    if {"brainstorm", "explore", "ideas", "design"} & goal_tokens:
        return "brainstorm"
    if {"debug", "fix", "bug"} & goal_tokens:
        return "debug"
    if {"test", "verify", "validation"} & goal_tokens:
        return "test"
    if {"deploy", "release", "ship"} & goal_tokens:
        return "deploy"
    if {"review", "audit", "pr"} & goal_tokens:
        return "review"
    return "default"


def _build_stage_plan(
    *,
    goal: str,
    goal_tokens: set[str],
    profile: dict,
    selected_skills: list[SkillCandidate],
    execution_mode: str,
    reflection_max_retries: int,
    verification_passes: int,
    feedback_adjustments: dict | None,
) -> tuple[list[dict], list[str]]:
    skill_names = [skill.name for skill in selected_skills]
    skill_sources = [skill.source for skill in selected_skills]
    stage_focus = _goal_kind(goal_tokens)
    stage_prefix = {
        "discover": "Discover",
        "plan": "Plan",
        "build": "Build",
        "review": "Review",
        "test": "Test",
        "ship": "Ship",
        "reflect": "Reflect",
    }

    if skill_names:
        skill_line = f"Top relevant skills: {', '.join(skill_names)}."
    else:
        skill_line = "Top relevant skills: none selected."

    stage_details: dict[str, dict[str, list[str]]] = {
        "discover": {
            "objectives": [
                "Read .agent/project_profile.yaml and .agent/context/project-context.md before taking action.",
                f"Confirm the project stage, app type, frameworks, and priorities for goal: {goal}.",
                skill_line,
            ],
            "acceptance_checks": [
                "Project profile and generated context are present or inferred without error.",
                "The ranked skill list is deterministic for the current goal and profile.",
                "Target tools and project shape are visible in the workflow output.",
            ],
            "evidence": [
                ".agent/project_profile.yaml",
                ".agent/context/project-context.md",
                ".agent/context/index.json",
            ],
        },
        "plan": {
            "objectives": [
                "Turn the goal into a minimal patch plan with explicit verification checkpoints.",
                "Name the touched files or subsystems before any edit is made.",
                "Record the chosen execution mode and retry budget for the run.",
            ],
            "acceptance_checks": [
                "The plan names concrete files, commands, or subsystems.",
                "Every planned step has at least one verification check.",
                "Planner-editor mode, when selected, is reflected in the workflow text.",
            ],
            "evidence": [
                "selected skill names",
                "execution mode",
                "reflection retry budget",
            ],
        },
        "build": {
            "objectives": [
                "Implement the smallest coherent change needed for the goal.",
                "Keep edits scoped to the selected files and avoid unrelated refactors.",
                "For debug goals, reproduce the issue and capture the failing behavior.",
                "For brainstorm goals, compare the candidate approaches and choose the recommended path.",
            ],
            "acceptance_checks": [
                "The patch changes only the files needed for the requested goal.",
                "The requested behavior is present in the generated workflow output.",
                "The implementation preserves the current command surface and backward compatibility.",
            ],
            "evidence": [
                "edited files",
                "goal-specific behavior",
                "workflow steps list",
            ],
        },
        "review": {
            "objectives": [
                "Inspect the changed files for correctness, regressions, and missing coverage.",
                "Summarize findings first when risks remain, then note any verification gaps.",
                "Validate that the workflow still reads cleanly as a handoff artifact.",
            ],
            "acceptance_checks": [
                "The review names concrete risks or confirms the change is safe.",
                "The review output is ordered and actionable for the next agent.",
                "No unrelated files or behaviors are introduced into the plan.",
            ],
            "evidence": [
                "changed files",
                "risk notes",
                "review summary",
            ],
        },
        "test": {
            "objectives": [
                "Run the relevant automated tests for the changed workflow behavior.",
                "Capture the exact command output or assertion evidence for the change.",
                "Prefer the smallest test surface that still proves the new stage structure.",
            ],
            "acceptance_checks": [
                "Targeted tests pass after the implementation change.",
                "The failure mode is observable if the stage structure regresses.",
                "The test suite still covers the existing `steps` list contract.",
            ],
            "evidence": [
                "test command output",
                "passing assertions",
                "existing compose compatibility",
            ],
        },
        "ship": {
            "objectives": [
                "Make the workflow output usable as a release-grade handoff artifact.",
                "Keep the command output deterministic for CLI and file-based use.",
                "Preserve the current release notes, rollback, and packaging signals.",
            ],
            "acceptance_checks": [
                "The generated workflow includes both stage structure and the legacy `steps` list.",
                "Compose output remains stable across repeated runs with the same inputs.",
                "The result can be written to a file without additional cleanup.",
            ],
            "evidence": [
                "workflow YAML output",
                "output file path",
                "deterministic render",
            ],
        },
            "reflect": {
            "objectives": [
                "Summarize what the evidence says about the current run.",
                "Carry forward the retry budget and feedback signals only when they exist.",
                "Use the observed results to inform the next iteration instead of guessing.",
            ],
            "acceptance_checks": [
                "Reflection text is grounded in the run's actual feedback or retry state.",
                "Any mode suggestion comes from the current evidence, not a dummy rule.",
                "The workflow keeps the same structure if no feedback is available.",
            ],
            "evidence": [
                "feedback artifact",
                "reflection retry count",
                "mode suggestion state",
            ],
        },
    }

    if stage_focus == "debug":
        stage_details["build"]["objectives"][2] = "Reproduce the issue and capture the failing behavior."
        stage_details["build"]["objectives"].insert(3, "Implement the fix with focused verification for the affected area.")
        stage_details["build"]["acceptance_checks"][0] = "Reproduce the issue and capture the failing behavior before the fix is applied."
        stage_details["build"]["acceptance_checks"][1] = "Implement the fix with focused verification for the affected area."
    elif stage_focus == "brainstorm":
        stage_details["plan"]["objectives"][0] = "Generate 2-3 credible approaches with explicit tradeoffs."
        stage_details["plan"]["objectives"].append("Choose the recommended path based on the current priorities and project stage.")
        stage_details["build"]["objectives"][3] = "Choose the recommended path based on the current priorities and project stage."
        stage_details["plan"]["acceptance_checks"].insert(1, "The workflow names at least one recommended path and its tradeoff.")
    elif stage_focus == "test":
        stage_details["test"]["objectives"][0] = "Identify the highest-risk behavior and the smallest reliable test surface."
        stage_details["test"]["objectives"].insert(1, "Run the relevant automated tests and record the evidence.")
        stage_details["test"]["acceptance_checks"][0] = "Run the relevant automated tests and record the evidence."
    elif stage_focus == "deploy":
        stage_details["ship"]["objectives"][0] = "Check release readiness against the current project stage, priorities, and target tools."
        stage_details["ship"]["objectives"].append("Confirm tests, documentation, and rollback notes before shipping.")
        stage_details["ship"]["acceptance_checks"][1] = "rollback notes or release checklist items are explicitly named."
    elif stage_focus == "review":
        stage_details["review"]["objectives"][0] = "Inspect the changed files for correctness, regressions, and release risks."
        stage_details["review"]["acceptance_checks"].insert(0, "Findings are ordered by severity when issues are present.")

    stages: list[dict] = []
    steps: list[str] = []
    for stage_name in WORKFLOW_STAGE_ORDER:
        detail = stage_details[stage_name]
        stage_entry = {
            "name": stage_name,
            "objective": detail["objectives"][0],
            "objectives": detail["objectives"],
            "acceptance_checks": detail["acceptance_checks"],
            "evidence": detail["evidence"],
            "summary": f"{stage_prefix[stage_name]} stage: {detail['objectives'][0]}",
        }
        stages.append(stage_entry)
        acceptance_fragment = "; ".join(detail["acceptance_checks"][:2])
        steps.append(f"{stage_prefix[stage_name]} stage: {detail['objectives'][0]} Acceptance: {acceptance_fragment}.")

    steps.insert(0, "Read .agent/project_profile.yaml and .agent/context/project-context.md.")
    steps.insert(1, "Confirm the requested goal against the current project stage and target tools.")
    if execution_mode == "planner-editor":
        steps.append("Planner phase: break the goal into a minimal patch plan with explicit acceptance checks.")
        steps.append("Planner phase: identify required files, risks, and verification checkpoints before edits.")
        steps.append("Editor phase: apply the approved plan in small diffs and keep changes scoped.")
    if skill_names:
        steps.append(f"Load the top relevant skills: {', '.join(skill_names)}.")
    if feedback_adjustments:
        budget_name = str(feedback_adjustments.get("resolved_slo_budget", {}).get("name", "default"))
        budget_thresholds = feedback_adjustments.get("resolved_slo_budget", {}).get("thresholds", {})
        if not isinstance(budget_thresholds, dict):
            budget_thresholds = {}
        breach_reasons = feedback_adjustments.get("breach_reasons", [])
        if not isinstance(breach_reasons, list):
            breach_reasons = []
        budget_line = (
            f"SLO budget: {budget_name} "
            f"(TACR floor {budget_thresholds.get('tacr_floor', 'n/a')}, "
            f"delta TACR floor {budget_thresholds.get('delta_tacr_floor', 'n/a')}, "
            f"interventions threshold {budget_thresholds.get('interventions_threshold', 'n/a')}, "
            f"latency threshold {budget_thresholds.get('latency_increase_threshold_ms', 'n/a')}, "
            f"cost threshold {budget_thresholds.get('cost_increase_threshold_usd', 'n/a')})."
        )
        if breach_reasons:
            budget_line += f" Breaches: {', '.join(str(reason) for reason in breach_reasons)}."
        steps.append(budget_line)
        steps.append(
            f"Feedback loop: rolling TACR was {feedback_adjustments['rolling_tacr']:g}% "
            f"across {feedback_adjustments['artifact_count']} artifacts; "
            f"delta TACR {feedback_adjustments['delta_tacr']:g}pp, "
            f"add {verification_passes} verification passes and up to {reflection_max_retries} reflection retries."
        )
        if execution_mode == "standard" and feedback_adjustments.get("mode_suggestion"):
            steps.append(
                "Planner-editor mode suggestion: recent eval trends crossed the guardrails; "
                "consider rerunning with --mode planner-editor."
            )
    if reflection_max_retries > 0:
        steps.append(
            f"Reflection loop: after failed verification, run self-critique and retry up to {reflection_max_retries} times."
        )
    steps.append(
        f"Verification loop: run {verification_passes} verification pass{'es' if verification_passes != 1 else ''} before completion."
    )
    steps.append("Run the most relevant test or validation command before completion.")
    return stages, steps


def build_workflow(
    goal: str,
    cwd: Path,
    max_skills: int = 5,
    *,
    execution_mode: str = "standard",
    reflection_max_retries: int = 0,
    feedback: dict | None = None,
) -> dict:
    profile = load_profile_or_default(cwd)
    context_summary = load_context_summary(cwd)
    selected_skills = select_skills_for_goal(goal, cwd, max_skills=max_skills)
    mode = execution_mode if execution_mode in {"standard", "planner-editor"} else "standard"
    retries = max(0, int(reflection_max_retries))
    verification_passes = 1
    feedback_adjustments = _feedback_adjustments(feedback) if feedback else None
    if feedback_adjustments:
        retries = max(retries, feedback_adjustments["reflection_max_retries"])
        verification_passes = max(verification_passes, feedback_adjustments["verification_passes"])

    goal_tokens = _tokenize(goal)
    stage = profile.get("project_stage", "unknown")
    app_type = profile.get("app_type", "application")
    frameworks = _safe_list(profile.get("frameworks"))
    priorities = _safe_list(profile.get("priorities"))
    stages, steps = _build_stage_plan(
        goal=goal,
        goal_tokens=goal_tokens,
        profile=profile,
        selected_skills=selected_skills,
        execution_mode=mode,
        reflection_max_retries=retries,
        verification_passes=verification_passes,
        feedback_adjustments=feedback_adjustments,
    )

    workflow = {
        "goal": goal,
        "execution_mode": mode,
        "reflection_max_retries": retries,
        "verification_passes": verification_passes,
        "profile": {
            "idea": profile.get("idea", "not-specified"),
            "project_stage": stage,
            "app_type": app_type,
            "frameworks": frameworks,
            "priorities": priorities,
        },
        "context_available": bool(context_summary),
        "skills": [skill.name for skill in selected_skills],
        "skill_sources": [skill.source for skill in selected_skills],
        "stages": stages,
        "steps": steps,
    }
    if feedback_adjustments:
        workflow["feedback"] = feedback_adjustments
        workflow["slo_budget"] = feedback_adjustments.get("resolved_slo_budget", {})
        workflow["breach_reasons"] = feedback_adjustments.get("breach_reasons", [])
        if feedback_adjustments.get("mode_suggestion"):
            workflow["mode_suggestion"] = feedback_adjustments["mode_suggestion"]
    return workflow


def _feedback_adjustments(feedback: dict) -> dict | None:
    if not isinstance(feedback, dict):
        return None

    summary = feedback.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    trend = feedback.get("trend", {})
    if not isinstance(trend, dict):
        trend = {}
    policy = feedback.get("policy", {})
    if not isinstance(policy, dict):
        policy = {}
    resolved_slo_budget = policy.get("resolved_slo_budget", {})
    if not isinstance(resolved_slo_budget, dict):
        resolved_slo_budget = {}
    planner_editor = policy.get("planner_editor", {})
    if not isinstance(planner_editor, dict):
        planner_editor = {}

    rolling_tacr = _coerce_float(summary.get("tacr"), 0.0)
    total_interventions = _coerce_float(summary.get("total_interventions"), 0.0)
    delta_tacr = _coerce_float(trend.get("delta_tacr"), 0.0) if _coerce_bool(trend.get("available")) else 0.0
    delta_latency = _coerce_float(trend.get("delta_avg_latency_ms"), 0.0) if _coerce_bool(trend.get("available")) else 0.0
    delta_cost = _coerce_float(trend.get("delta_avg_cost_usd"), 0.0) if _coerce_bool(trend.get("available")) else 0.0

    slo_thresholds = resolved_slo_budget.get("thresholds", {})
    if not isinstance(slo_thresholds, dict):
        slo_thresholds = {}
    slo_caps = resolved_slo_budget.get("caps", {})
    if not isinstance(slo_caps, dict):
        slo_caps = {}

    tacr_floor = _coerce_float(slo_thresholds.get("tacr_floor"), _coerce_float(policy.get("tacr_floor"), 75.0))
    delta_tacr_floor = _coerce_float(
        slo_thresholds.get("delta_tacr_floor"), _coerce_float(policy.get("delta_tacr_floor"), 0.0)
    )
    interventions_threshold = max(
        0,
        _coerce_int(slo_thresholds.get("interventions_threshold"), _coerce_int(policy.get("interventions_threshold"), 3)),
    )
    latency_increase_threshold_ms = _coerce_float(
        slo_thresholds.get("latency_increase_threshold_ms"),
        _coerce_float(policy.get("latency_increase_threshold_ms"), 0.0),
    )
    cost_increase_threshold_usd = _coerce_float(
        slo_thresholds.get("cost_increase_threshold_usd"),
        _coerce_float(policy.get("cost_increase_threshold_usd"), 0.0),
    )

    verification_pass_floor = max(
        1,
        _coerce_int(slo_caps.get("verification_pass_floor"), _coerce_int(policy.get("verification_pass_floor"), 1)),
    )
    verification_pass_cap = max(
        verification_pass_floor,
        _coerce_int(slo_caps.get("verification_pass_cap"), _coerce_int(policy.get("verification_pass_cap"), 4)),
    )
    reflection_retry_cap = max(
        0,
        _coerce_int(slo_caps.get("reflection_retry_cap"), _coerce_int(policy.get("reflection_retry_cap"), 3)),
    )
    allow_mode_switch = _coerce_bool(slo_caps.get("allow_mode_switch"), True)

    breaches: list[dict] = []

    def add_breach(metric: str, actual: float, threshold: float, comparator: str, unit: str, reason: str) -> None:
        breaches.append(
            {
                "metric": metric,
                "actual": actual,
                "threshold": threshold,
                "comparator": comparator,
                "unit": unit,
                "reason": reason,
            }
        )

    if rolling_tacr < tacr_floor:
        add_breach(
            "tacr",
            rolling_tacr,
            tacr_floor,
            "<",
            "%",
            f"rolling TACR {rolling_tacr:g}% below floor {tacr_floor:g}%",
        )
    if delta_tacr < delta_tacr_floor:
        add_breach(
            "delta_tacr",
            delta_tacr,
            delta_tacr_floor,
            "<",
            "pp",
            f"delta TACR {delta_tacr:g}pp below floor {delta_tacr_floor:g}pp",
        )
    if total_interventions >= interventions_threshold:
        add_breach(
            "interventions",
            total_interventions,
            float(interventions_threshold),
            ">=",
            "",
            f"rolling interventions {total_interventions:g} at or above threshold {interventions_threshold:g}",
        )
    if delta_latency > latency_increase_threshold_ms:
        add_breach(
            "latency",
            delta_latency,
            latency_increase_threshold_ms,
            ">",
            "ms",
            f"latency increase {delta_latency:g}ms above threshold {latency_increase_threshold_ms:g}ms",
        )
    if delta_cost > cost_increase_threshold_usd:
        add_breach(
            "cost",
            delta_cost,
            cost_increase_threshold_usd,
            ">",
            "USD",
            f"cost increase ${delta_cost:g} above threshold ${cost_increase_threshold_usd:g}",
        )

    risk_score = len(breaches)

    if risk_score == 0:
        return None

    verification_passes = min(verification_pass_cap, max(verification_pass_floor, 1 + risk_score))
    reflection_retries = min(reflection_retry_cap, risk_score)
    mode_suggestion = None
    if allow_mode_switch and _coerce_bool(planner_editor.get("enabled"), True):
        planner_risk_threshold = max(1, _coerce_int(planner_editor.get("risk_threshold"), 2))
        planner_tacr_floor = _coerce_float(planner_editor.get("tacr_floor"), 70.0)
        planner_delta_floor = _coerce_float(planner_editor.get("delta_tacr_floor"), 0.0)
        planner_interventions_threshold = _coerce_float(planner_editor.get("interventions_threshold"), 2.0)
        if (
            risk_score >= planner_risk_threshold
            or rolling_tacr < planner_tacr_floor
            or delta_tacr < planner_delta_floor
            or total_interventions >= planner_interventions_threshold
        ):
            mode_suggestion = "planner-editor"

    return {
        "source": str(feedback.get("source", "unknown")),
        "window": _coerce_int(feedback.get("window"), 0),
        "requested_window": _coerce_int(feedback.get("requested_window"), 0),
        "artifact_count": _coerce_int(feedback.get("artifact_count"), 0),
        "rolling_tacr": rolling_tacr,
        "total_interventions": total_interventions,
        "delta_tacr": delta_tacr if _coerce_bool(trend.get("available")) else None,
        "delta_avg_latency_ms": delta_latency if _coerce_bool(trend.get("available")) else None,
        "delta_avg_cost_usd": delta_cost if _coerce_bool(trend.get("available")) else None,
        "resolved_slo_budget": resolved_slo_budget,
        "breaches": breaches,
        "breach_reasons": [breach["reason"] for breach in breaches],
        "verification_passes": verification_passes,
        "reflection_max_retries": reflection_retries,
        "allow_mode_switch": allow_mode_switch,
        "mode_suggestion": mode_suggestion,
        "risk_score": risk_score,
    }


def workflow_bundle_definitions(cwd: Path) -> list[tuple[str, str]]:
    profile = load_profile_or_default(cwd)
    app_type = profile.get("app_type", "application")
    framework_text = ", ".join(_safe_list(profile.get("frameworks"))) or ", ".join(_safe_list(profile.get("languages")))
    return [
        ("discover-project", f"discover project context {app_type} {framework_text}"),
        ("brainstorm", f"brainstorm implementation approaches for {app_type} {framework_text}"),
        ("plan-feature", f"plan feature for {app_type} {framework_text}"),
        ("implement-feature", f"implement feature for {app_type} {framework_text}"),
        ("debug-issue", f"debug issue for {app_type} {framework_text}"),
        ("review-changes", f"review changes for {app_type} {framework_text}"),
        ("test-changes", f"test and verify changes for {app_type} {framework_text}"),
        ("deploy-checklist", f"deploy release checklist for {app_type} {framework_text}"),
        ("refactor", f"refactor project structure and technical debt for {app_type} {framework_text}"),
        ("debug", f"debug complex runtime issues for {app_type} {framework_text}"),
        ("test", f"test and verify implementation for {app_type} {framework_text}"),
        ("doc", f"update and synchronize documentation for {app_type} {framework_text}"),
        ("audit", f"perform security and performance audit for {app_type} {framework_text}"),
        ("lint", f"run linter and fix stylistic issues for {app_type} {framework_text}"),
        ("compose", f"compose multiple skills and workflows for {app_type} {framework_text}"),
        ("evolve", f"evolve and improve skill instructions for {app_type} {framework_text}"),
        ("align", f"align project instructions and rules with the profile for {app_type} {framework_text}"),
        ("profile", f"inspect and tune the project profile for {app_type} {framework_text}"),
        ("report", f"generate a progress and readiness report for {app_type} {framework_text}"),
        ("sync", f"sync local configuration and skills for {app_type} {framework_text}"),
        ("autonomous", f"run an autonomous agent loop for {app_type} {framework_text}"),
        ("context", f"index and optimize context for {app_type} {framework_text}"),
        ("verify", f"verify project health and requirements for {app_type} {framework_text}"),
        ("review", f"review code and architecture for {app_type} {framework_text}"),
        ("bootstrap", f"bootstrap a new module or service for {app_type} {framework_text}"),
        ("migrate", f"plan and execute migration for {app_type} {framework_text}"),
        ("benchmark", f"benchmark performance for {app_type} {framework_text}"),
        ("security", f"audit and harden security for {app_type} {framework_text}"),
        ("performance", f"profile and optimize performance for {app_type} {framework_text}"),
        ("cleanup", f"cleanup obsolete code and artifacts for {app_type} {framework_text}"),
        ("search", f"search and research repository for {app_type} {framework_text}"),
        ("explain", f"explain project architecture and logic for {app_type} {framework_text}"),
        ("ready", f"check production readiness for {app_type} {framework_text}"),
    ]


def workflow_markdown(name: str, workflow: dict) -> str:
    lines = [
        f"# Workflow: {name}",
        "",
        f"- **Goal**: {workflow['goal']}",
        f"- **Idea**: {workflow['profile']['idea']}",
        f"- **Stage**: {workflow['profile']['project_stage']}",
        f"- **App type**: {workflow['profile']['app_type']}",
        f"- **Frameworks**: {', '.join(workflow['profile']['frameworks']) if workflow['profile']['frameworks'] else 'none-detected'}",
        f"- **Priorities**: {', '.join(workflow['profile']['priorities']) if workflow['profile']['priorities'] else 'none-specified'}",
        f"- **Skills**: {', '.join(workflow['skills']) if workflow['skills'] else 'none'}",
        "",
        "## Stages",
        "",
    ]
    
    for stage in workflow.get("stages", []):
        lines.append(f"### {stage['name'].title()}")
        lines.append(f"> {stage['objective']}")
        lines.append("")
        lines.append("**Objectives**:")
        for obj in stage.get("objectives", []):
            lines.append(f"- {obj}")
        lines.append("")
        lines.append("**Acceptance Checks**:")
        for check in stage.get("acceptance_checks", []):
            lines.append(f"- [ ] {check}")
        lines.append("")
        lines.append("**Evidence**:")
        for ev in stage.get("evidence", []):
            lines.append(f"- {ev}")
        lines.append("")

    lines.append("## Steps Summary")
    lines.extend([f"{index}. {step}" for index, step in enumerate(workflow["steps"], start=1)])
    return "\n".join(lines) + "\n"
