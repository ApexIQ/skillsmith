from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from . import TEMPLATE_DIR, console
from .init import _infer_project_profile
from .rendering import load_project_profile

POLICY_RELATIVE_PATH = ".agent/evals/policy.json"
PACKS_RELATIVE_DIR = ".agent/evals/packs"
TEMPLATE_POLICY_PATH = TEMPLATE_DIR / POLICY_RELATIVE_PATH
TEMPLATE_PACKS_DIR = TEMPLATE_DIR / PACKS_RELATIVE_DIR
POLICY_BUDGET_CONTAINER_KEYS = ("budget_profiles", "threshold_profiles", "app_type_budgets", "app_type_profiles", "profiles")
POLICY_PROFILE_SELECTOR_KEYS = ("selected_budget_profile", "budget_profile", "default_budget_profile", "profile")
EVAL_THRESHOLD_KEYS = ("min_tacr_delta", "max_latency_increase_ms", "max_cost_increase_usd")
POLICY_SLO_BUDGET_CONTAINER_KEYS = ("slo_budgets", "slo_budget_profiles", "slo_profiles")
POLICY_SLO_PROFILE_SELECTOR_KEYS = ("slo_budget", "slo_budget_name", "slo_budget_profile")
SLO_THRESHOLD_KEYS = (
    "tacr_floor",
    "delta_tacr_floor",
    "interventions_threshold",
    "latency_increase_threshold_ms",
    "cost_increase_threshold_usd",
)
SLO_CAP_KEYS = ("verification_pass_floor", "verification_pass_cap", "reflection_retry_cap", "allow_mode_switch")


def _now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_artifact(path: Path) -> dict | None:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return payload
    return None


def _load_policy_payload(path: Path) -> dict | None:
    payload = _load_json(path)
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


def _load_merged_policy_payload(cwd: Path) -> dict:
    merged: dict = {}
    if TEMPLATE_POLICY_PATH.exists():
        builtin_payload = _load_policy_payload(TEMPLATE_POLICY_PATH)
        if isinstance(builtin_payload, dict):
            merged = builtin_payload

    local_policy_path = cwd / POLICY_RELATIVE_PATH
    if local_policy_path.exists():
        local_payload = _load_policy_payload(local_policy_path)
        if isinstance(local_payload, dict):
            merged = _merge_dicts(merged, local_payload)
    return merged


def _load_runs(path: Path) -> list[dict]:
    payload = _load_json(path)
    if payload is None:
        return []
    if isinstance(payload, dict):
        runs = payload.get("runs", [])
    elif isinstance(payload, list):
        runs = payload
    else:
        runs = []
    return [item for item in runs if isinstance(item, dict)]


def _resolve_pack_path(cwd: Path, pack: str) -> Path:
    candidate = Path(pack)
    if candidate.is_absolute():
        return candidate
    direct = cwd / pack
    if direct.exists():
        return direct
    pack_name = candidate.name if candidate.suffix else f"{pack}.json"
    local_pack = cwd / PACKS_RELATIVE_DIR / pack_name
    if local_pack.exists():
        return local_pack
    return TEMPLATE_PACKS_DIR / pack_name


def _policy_pack_name(payload: dict) -> str | None:
    for key in ("pack", "default_pack"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name") or value.get("pack")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    benchmark_pack = payload.get("benchmark_pack")
    if isinstance(benchmark_pack, str) and benchmark_pack.strip():
        return benchmark_pack.strip()
    if isinstance(benchmark_pack, dict):
        nested = benchmark_pack.get("name") or benchmark_pack.get("pack")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _policy_thresholds(payload: dict) -> dict[str, float | None]:
    thresholds = {key: None for key in EVAL_THRESHOLD_KEYS}
    threshold_payload = payload.get("thresholds")
    if not isinstance(threshold_payload, dict):
        threshold_payload = payload
    for key in EVAL_THRESHOLD_KEYS:
        if key in threshold_payload:
            thresholds[key] = _coerce_float(threshold_payload.get(key))
    return thresholds


def _slo_threshold_defaults(payload: dict | None = None) -> dict[str, float | None]:
    compose_payload = payload.get("compose", {}) if isinstance(payload, dict) and isinstance(payload.get("compose"), dict) else {}
    return {
        "tacr_floor": _coerce_float(compose_payload.get("tacr_floor"), 75.0),
        "delta_tacr_floor": _coerce_float(compose_payload.get("delta_tacr_floor"), 0.0),
        "interventions_threshold": float(max(0, _coerce_int(compose_payload.get("interventions_threshold"), 3))),
        "latency_increase_threshold_ms": _coerce_float(compose_payload.get("latency_increase_threshold_ms"), 0.0),
        "cost_increase_threshold_usd": _coerce_float(compose_payload.get("cost_increase_threshold_usd"), 0.0),
    }


def _slo_cap_defaults(payload: dict | None = None) -> dict[str, int | bool]:
    compose_payload = payload.get("compose", {}) if isinstance(payload, dict) and isinstance(payload.get("compose"), dict) else {}
    return {
        "verification_pass_floor": max(1, _coerce_int(compose_payload.get("verification_pass_floor"), 1)),
        "verification_pass_cap": max(1, _coerce_int(compose_payload.get("verification_pass_cap"), 4)),
        "reflection_retry_cap": max(0, _coerce_int(compose_payload.get("reflection_retry_cap"), 3)),
        "allow_mode_switch": True,
    }


def _read_budget_reference(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "budget", "profile", "slo_budget"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _looks_like_slo_budget(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if any(key in payload for key in SLO_THRESHOLD_KEYS + SLO_CAP_KEYS):
        return True
    thresholds = payload.get("thresholds")
    if isinstance(thresholds, dict) and any(key in thresholds for key in SLO_THRESHOLD_KEYS):
        return True
    caps = payload.get("caps")
    return isinstance(caps, dict) and any(key in caps for key in SLO_CAP_KEYS)


def _slo_budgets_from_payload(payload: dict) -> dict[str, dict]:
    budgets: dict[str, dict] = {}
    for key in POLICY_SLO_BUDGET_CONTAINER_KEYS:
        candidate = payload.get(key)
        if not isinstance(candidate, dict):
            continue
        for budget_name, budget_payload in candidate.items():
            if _looks_like_slo_budget(budget_payload):
                budgets[str(budget_name)] = dict(budget_payload)
    return budgets


def _budget_profile_slo_budget_name(profile_payload: dict | None) -> str | None:
    if not isinstance(profile_payload, dict):
        return None
    for key in POLICY_SLO_PROFILE_SELECTOR_KEYS:
        ref = _read_budget_reference(profile_payload.get(key))
        if ref:
            return ref
    return None


def _slo_budget_thresholds(budget_payload: dict | None, fallback: dict[str, float | None] | None = None) -> dict[str, float | None]:
    thresholds = dict(fallback or _slo_threshold_defaults(None))
    if not isinstance(budget_payload, dict):
        return thresholds
    threshold_payload = budget_payload.get("thresholds") if isinstance(budget_payload.get("thresholds"), dict) else budget_payload
    for key in SLO_THRESHOLD_KEYS:
        value = threshold_payload.get(key) if isinstance(threshold_payload, dict) else None
        if value is not None:
            thresholds[key] = _coerce_float(value)
    return thresholds


def _slo_budget_caps(budget_payload: dict | None, fallback: dict[str, int | bool] | None = None) -> dict[str, int | bool]:
    caps = dict(fallback or _slo_cap_defaults(None))
    if not isinstance(budget_payload, dict):
        return caps
    cap_payload = budget_payload.get("caps") if isinstance(budget_payload.get("caps"), dict) else budget_payload
    alias_map = {
        "verification_pass_floor": ("verification_pass_floor",),
        "verification_pass_cap": ("verification_pass_cap", "max_verification_passes"),
        "reflection_retry_cap": ("reflection_retry_cap", "max_reflection_retries"),
        "allow_mode_switch": ("allow_mode_switch", "mode_switch_enabled"),
    }
    for canonical_key, aliases in alias_map.items():
        for key in aliases:
            if isinstance(cap_payload, dict) and key in cap_payload:
                value = cap_payload.get(key)
                if canonical_key == "allow_mode_switch":
                    caps[canonical_key] = _coerce_bool(value, bool(caps.get(canonical_key, True)))
                else:
                    caps[canonical_key] = max(0, _coerce_int(value, int(caps.get(canonical_key, 0))))
                break
    return caps


def _select_slo_budget(
    policy_payload: dict,
    *,
    app_type: str | None,
    selected_budget_profile_name: str | None,
    selected_budget_profile_payload: dict | None,
) -> tuple[str | None, dict | None, str]:
    budgets = _slo_budgets_from_payload(policy_payload)
    base_thresholds = _slo_threshold_defaults(policy_payload)
    base_caps = _slo_cap_defaults(policy_payload)

    profile_budget_name = _budget_profile_slo_budget_name(selected_budget_profile_payload)
    selector = ""
    if profile_budget_name and profile_budget_name in budgets:
        selector = f"budget_profiles.{selected_budget_profile_name}.slo_budget"
        payload = budgets[profile_budget_name]
        return profile_budget_name, {
            "name": profile_budget_name,
            "selector": selector,
            "source": selector,
            "thresholds": _slo_budget_thresholds(payload, fallback=base_thresholds),
            "caps": _slo_budget_caps(payload, fallback=base_caps),
        }, selector

    if selected_budget_profile_name and selected_budget_profile_name in budgets:
        selector = f"slo_budgets.{selected_budget_profile_name}"
        payload = budgets[selected_budget_profile_name]
        return selected_budget_profile_name, {
            "name": selected_budget_profile_name,
            "selector": selector,
            "source": selector,
            "thresholds": _slo_budget_thresholds(payload, fallback=base_thresholds),
            "caps": _slo_budget_caps(payload, fallback=base_caps),
        }, selector

    for alias in _budget_profile_aliases(app_type):
        if alias in budgets:
            selector = f"app_type.{alias}"
            payload = budgets[alias]
            return alias, {
                "name": alias,
                "selector": selector,
                "source": selector,
                "thresholds": _slo_budget_thresholds(payload, fallback=base_thresholds),
                "caps": _slo_budget_caps(payload, fallback=base_caps),
            }, selector

    if selected_budget_profile_payload and _looks_like_slo_budget(selected_budget_profile_payload):
        fallback_name = selected_budget_profile_name or "selected-budget-profile"
        selector = f"budget_profiles.{selected_budget_profile_name or 'selected'}.inline"
        return fallback_name, {
            "name": fallback_name,
            "selector": selector,
            "source": selector,
            "thresholds": _slo_budget_thresholds(selected_budget_profile_payload, fallback=base_thresholds),
            "caps": _slo_budget_caps(selected_budget_profile_payload, fallback=base_caps),
        }, selector

    selector = "compose.defaults"
    return "default", {
        "name": "default",
        "selector": selector,
        "source": selector,
        "thresholds": base_thresholds,
        "caps": base_caps,
    }, selector


def _policy_state_from_payload(payload: dict, source: Path) -> dict:
    return {
        "source": source.as_posix(),
        "default_pack": _policy_pack_name(payload),
        "default_thresholds": _policy_thresholds(payload),
    }


def _merge_policy_states(base: dict | None, override: dict | None) -> dict:
    if not base and not override:
        return {"source": "", "default_pack": None, "default_thresholds": {key: None for key in EVAL_THRESHOLD_KEYS}}
    if not base:
        return override or {"source": "", "default_pack": None, "default_thresholds": {key: None for key in EVAL_THRESHOLD_KEYS}}
    if not override:
        return base

    merged_thresholds = dict(base.get("default_thresholds", {}))
    for key, value in override.get("default_thresholds", {}).items():
        if value is not None:
            merged_thresholds[key] = value

    merged = {
        "source": override.get("source") or base.get("source", ""),
        "default_pack": override.get("default_pack") or base.get("default_pack"),
        "default_thresholds": merged_thresholds,
    }
    return merged


def _load_policy_state(cwd: Path) -> dict:
    builtin = None
    if TEMPLATE_POLICY_PATH.exists():
        builtin_payload = _load_policy_payload(TEMPLATE_POLICY_PATH)
        if isinstance(builtin_payload, dict):
            builtin = _policy_state_from_payload(builtin_payload, TEMPLATE_POLICY_PATH)

    local = None
    local_policy_path = cwd / POLICY_RELATIVE_PATH
    if local_policy_path.exists():
        local_payload = _load_policy_payload(local_policy_path)
        if isinstance(local_payload, dict):
            local = _policy_state_from_payload(local_payload, local_policy_path)

    return _merge_policy_states(builtin, local)


def _current_project_profile(cwd: Path) -> dict:
    try:
        profile = load_project_profile(cwd)
        if isinstance(profile, dict) and profile:
            return profile
    except Exception:
        pass
    return _infer_project_profile(cwd)


def _looks_like_budget_profile(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if any(key in payload for key in EVAL_THRESHOLD_KEYS) or any(key in payload for key in POLICY_SLO_PROFILE_SELECTOR_KEYS):
        return True
    threshold_payload = payload.get("thresholds")
    return isinstance(threshold_payload, dict) and (
        any(key in threshold_payload for key in EVAL_THRESHOLD_KEYS)
        or any(key in threshold_payload for key in SLO_THRESHOLD_KEYS)
        or any(key in threshold_payload for key in POLICY_SLO_PROFILE_SELECTOR_KEYS)
    )


def _budget_profiles_from_payload(payload: dict) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for key in POLICY_BUDGET_CONTAINER_KEYS:
        candidate = payload.get(key)
        if not isinstance(candidate, dict):
            continue
        for profile_name, profile_payload in candidate.items():
            if _looks_like_budget_profile(profile_payload):
                profiles[str(profile_name)] = dict(profile_payload)
    return profiles


def _budget_profile_aliases(app_type: str | None) -> list[str]:
    normalized = str(app_type or "").strip().lower()
    if not normalized:
        return []
    aliases = [normalized]
    normalized_dash = normalized.replace("_", "-")
    normalized_underscore = normalized.replace("-", "_")
    aliases.extend([normalized_dash, normalized_underscore, normalized.replace("-", ""), normalized.replace("_", "")])
    alias_map = {
        "web-app": ["web", "webapp"],
        "fullstack-app": ["fullstack", "fullstack-app", "fullstackapp", "web"],
        "api-service": ["api", "backend", "service", "apiservice"],
        "cli-tool": ["cli", "command-line", "commandline", "clitool"],
        "library": ["lib", "package"],
    }
    aliases.extend(alias_map.get(normalized_dash, []))
    aliases.extend(alias_map.get(normalized_underscore, []))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _select_budget_profile(payload: dict, app_type: str | None) -> tuple[str | None, dict | None, str]:
    profiles = _budget_profiles_from_payload(payload)
    if not profiles:
        return None, None, ""

    selector_value = None
    selector_name = ""
    for key in POLICY_PROFILE_SELECTOR_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            selector_value = value.strip()
            selector_name = key
            break

    if selector_value and selector_value in profiles:
        return selector_value, profiles[selector_value], selector_name

    for alias in _budget_profile_aliases(app_type):
        if alias in profiles:
            return alias, profiles[alias], selector_name

    for fallback in ("default", "base"):
        if fallback in profiles:
            return fallback, profiles[fallback], selector_name

    profile_name, profile_payload = next(iter(profiles.items()))
    return profile_name, profile_payload, selector_name


def _budget_profile_thresholds(profile_payload: dict | None) -> dict[str, float | None]:
    if not isinstance(profile_payload, dict):
        return {key: None for key in EVAL_THRESHOLD_KEYS}
    threshold_payload = profile_payload.get("thresholds")
    if isinstance(threshold_payload, dict):
        return {key: _coerce_float(threshold_payload.get(key)) if key in threshold_payload else None for key in EVAL_THRESHOLD_KEYS}
    return {key: _coerce_float(profile_payload.get(key)) if key in profile_payload else None for key in EVAL_THRESHOLD_KEYS}


def _budget_profile_pack(profile_payload: dict | None) -> str | None:
    if not isinstance(profile_payload, dict):
        return None
    for key in ("pack", "default_pack", "benchmark_pack"):
        value = profile_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name") or value.get("pack")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _builtin_pack_specs() -> list[dict[str, Any]]:
    if not TEMPLATE_PACKS_DIR.exists():
        return []
    specs: list[dict[str, Any]] = []
    for path in sorted(TEMPLATE_PACKS_DIR.glob("*.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        tasks = payload.get("tasks", [])
        specs.append(
            {
                "name": str(payload.get("name", path.stem)),
                "description": str(payload.get("description", "")),
                "task_count": len([task for task in tasks if isinstance(task, dict)]),
                "pack_path": path.as_posix(),
            }
        )
    return specs


def _load_pack(cwd: Path, pack: str | None) -> dict | None:
    if not pack:
        return None
    pack_path = _resolve_pack_path(cwd, pack)
    payload = _load_json(pack_path)
    if not isinstance(payload, dict):
        return None
    tasks = payload.get("tasks", [])
    payload["tasks"] = [task for task in tasks if isinstance(task, dict)]
    payload["pack_path"] = pack_path.as_posix()
    return payload


def _resolve_eval_policy(
    cwd: Path,
    *,
    pack: str | None,
    min_tacr_delta: float | None,
    max_latency_increase_ms: float | None,
    max_cost_increase_usd: float | None,
    no_ci_policy: bool,
) -> dict:
    policy_state = _load_policy_state(cwd)
    policy_payload = _load_merged_policy_payload(cwd)
    project_profile = _current_project_profile(cwd)
    app_type = str(project_profile.get("app_type", "")).strip().lower() or None
    selected_budget_profile_name, selected_budget_profile_payload, budget_profile_selector = _select_budget_profile(
        policy_payload,
        app_type,
    )
    selected_slo_budget_name, selected_slo_budget_payload, slo_budget_selector = _select_slo_budget(
        policy_payload,
        app_type=app_type,
        selected_budget_profile_name=selected_budget_profile_name,
        selected_budget_profile_payload=selected_budget_profile_payload,
    )
    ci_enforced = _coerce_bool(os.environ.get("CI"))
    selected_profile_pack = _budget_profile_pack(selected_budget_profile_payload)
    effective_pack = pack if pack is not None else selected_profile_pack or policy_state.get("default_pack")
    explicit_thresholds = {
        "min_tacr_delta": min_tacr_delta,
        "max_latency_increase_ms": max_latency_increase_ms,
        "max_cost_increase_usd": max_cost_increase_usd,
    }
    selected_profile_thresholds = _budget_profile_thresholds(selected_budget_profile_payload)
    selected_slo_budget_thresholds = dict(selected_slo_budget_payload.get("thresholds", {})) if isinstance(selected_slo_budget_payload, dict) else {}
    selected_slo_budget_caps = dict(selected_slo_budget_payload.get("caps", {})) if isinstance(selected_slo_budget_payload, dict) else {}
    gate_enabled = any(value is not None for value in explicit_thresholds.values()) or (ci_enforced and not no_ci_policy)
    effective_thresholds = {}
    if gate_enabled:
        effective_thresholds = dict(policy_state.get("default_thresholds", {}))
        for key, value in selected_slo_budget_thresholds.items():
            if key in effective_thresholds and value is not None:
                effective_thresholds[key] = value
        for key, value in selected_profile_thresholds.items():
            if value is not None:
                effective_thresholds[key] = value
        for key, value in explicit_thresholds.items():
            if value is not None:
                effective_thresholds[key] = value

    policy_state = {
        "source": policy_state.get("source", ""),
        "default_pack": policy_state.get("default_pack"),
        "default_thresholds": policy_state.get("default_thresholds", {key: None for key in EVAL_THRESHOLD_KEYS}),
        "app_type": app_type or "project",
        "selected_budget_profile": selected_budget_profile_name,
        "selected_budget_profile_selector": budget_profile_selector or None,
        "selected_budget_profile_thresholds": selected_profile_thresholds,
        "selected_budget_profile_pack": selected_profile_pack,
        "selected_slo_budget": selected_slo_budget_name,
        "selected_slo_budget_selector": slo_budget_selector or None,
        "selected_slo_budget_thresholds": selected_slo_budget_thresholds,
        "selected_slo_budget_caps": selected_slo_budget_caps,
        "resolved_slo_budget": selected_slo_budget_payload,
        "ci_enforced": ci_enforced and not no_ci_policy,
        "opt_out": no_ci_policy,
    }

    return {
        "pack": effective_pack,
        "policy": policy_state,
        "thresholds": effective_thresholds,
        "gate_enabled": gate_enabled,
    }


def _resolve_runs_source(cwd: Path, input_path: str, pack_payload: dict | None) -> Path:
    if input_path != ".agent/evals/runs.json":
        return cwd / input_path
    if not pack_payload:
        return cwd / input_path
    mapped = str(pack_payload.get("runs_file", "")).strip()
    if not mapped:
        return cwd / input_path
    mapped_path = Path(mapped)
    if mapped_path.is_absolute():
        return mapped_path
    if mapped.startswith("."):
        return cwd / mapped
    return cwd / ".agent" / "evals" / mapped


def _pack_task_summary(pack_payload: dict | None, runs: list[dict]) -> dict:
    if not pack_payload:
        return {}
    tasks = pack_payload.get("tasks", [])
    task_ids = {str(task.get("id")) for task in tasks if task.get("id")}
    seen_ids = {str(run.get("task_id")) for run in runs if run.get("task_id")}
    covered = len(task_ids & seen_ids) if task_ids else 0
    return {
        "pack_name": str(pack_payload.get("name", Path(str(pack_payload.get("pack_path", "pack"))).stem)),
        "pack_path": str(pack_payload.get("pack_path", "")),
        "total_tasks": len(task_ids),
        "tasks_with_runs": covered,
    }


def _summarize_runs(runs: list[dict], pack_payload: dict | None = None) -> dict:
    total = len(runs)
    if total == 0:
        summary = {
            "total_runs": 0,
            "successful_runs": 0,
            "tacr": 0.0,
            "avg_latency_ms": 0,
            "avg_cost_usd": 0.0,
            "total_interventions": 0,
        }
    else:
        successful = 0
        total_latency = 0
        total_cost = 0.0
        total_interventions = 0
        for run in runs:
            tests_passed = _coerce_bool(run.get("tests_passed"))
            policy_passed = _coerce_bool(run.get("policy_passed"))
            rollback_required = _coerce_bool(run.get("rollback_required"))
            if tests_passed and policy_passed and not rollback_required:
                successful += 1
            total_latency += _coerce_int(run.get("latency_ms"), 0)
            total_cost += _coerce_float(run.get("cost_usd"), 0.0)
            total_interventions += _coerce_int(run.get("interventions"), 0)
        summary = {
            "total_runs": total,
            "successful_runs": successful,
            "tacr": round((successful / total) * 100, 2),
            "avg_latency_ms": round(total_latency / total),
            "avg_cost_usd": round(total_cost / total, 4),
            "total_interventions": total_interventions,
        }

    if pack_payload:
        summary["benchmark_pack"] = _pack_task_summary(pack_payload, runs)
    return summary


def _artifact_files(output_dir: Path) -> list[Path]:
    candidates: list[tuple[str, float, str, Path]] = []
    for path in output_dir.glob("eval-*.json"):
        if not path.is_file():
            continue
        payload = _load_artifact(path)
        generated_at = ""
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at", "") or "")
        candidates.append((generated_at, path.stat().st_mtime, path.name, path))
    return [item[3] for item in sorted(candidates, key=lambda item: (item[0], item[1], item[2]))]


def _trend_from_payload(current_summary: dict, baseline_payload: dict | None, baseline_label: str) -> dict:
    if not isinstance(baseline_payload, dict):
        return {"available": False, "baseline_artifact": baseline_label}
    baseline_summary = baseline_payload.get("summary", {})
    if not isinstance(baseline_summary, dict):
        return {"available": False, "baseline_artifact": baseline_label}
    return {
        "available": True,
        "baseline_artifact": baseline_label,
        "baseline_generated_at": baseline_payload.get("generated_at"),
        "delta_tacr": round(_coerce_float(current_summary.get("tacr")) - _coerce_float(baseline_summary.get("tacr")), 2),
        "delta_avg_latency_ms": round(
            _coerce_float(current_summary.get("avg_latency_ms")) - _coerce_float(baseline_summary.get("avg_latency_ms")), 2
        ),
        "delta_avg_cost_usd": round(
            _coerce_float(current_summary.get("avg_cost_usd")) - _coerce_float(baseline_summary.get("avg_cost_usd")), 4
        ),
    }


def _trend_from_previous(output_dir: Path, current_summary: dict) -> dict:
    files = _artifact_files(output_dir)
    if not files:
        return {"available": False}
    previous_payload = _load_artifact(files[-1])
    if not isinstance(previous_payload, dict):
        return {"available": False}
    return _trend_from_payload(current_summary, previous_payload, files[-1].name)


def _resolve_baseline_artifact(cwd: Path, output_dir: Path, baseline_path: str | None) -> tuple[dict | None, str]:
    if baseline_path:
        resolved = Path(baseline_path)
        if not resolved.is_absolute():
            resolved = cwd / resolved
        return _load_artifact(resolved), resolved.as_posix()
    files = _artifact_files(output_dir)
    if not files:
        return None, ""
    previous_path = files[-1]
    return _load_artifact(previous_path), previous_path.name


def _evaluate_gate(
    trend: dict,
    *,
    min_tacr_delta: float | None,
    max_latency_increase_ms: float | None,
    max_cost_increase_usd: float | None,
) -> dict:
    thresholds_enabled = any(
        value is not None for value in (min_tacr_delta, max_latency_increase_ms, max_cost_increase_usd)
    )
    if not thresholds_enabled:
        return {"enabled": False, "passed": True, "checks": []}
    if not trend.get("available"):
        return {
            "enabled": True,
            "passed": False,
            "baseline_available": False,
            "checks": [],
            "failures": ["baseline artifact unavailable"],
        }

    checks: list[dict] = []
    failures: list[str] = []

    def add_check(name: str, actual: float, threshold: float, passed: bool, unit: str, comparator: str) -> None:
        checks.append(
            {
                "name": name,
                "actual": actual,
                "threshold": threshold,
                "passed": passed,
                "unit": unit,
                "comparator": comparator,
            }
        )
        if not passed:
            failures.append(f"{name} {actual}{unit} {comparator} {threshold}{unit}")

    delta_tacr = _coerce_float(trend.get("delta_tacr"))
    if min_tacr_delta is not None:
        add_check("TACR delta", delta_tacr, min_tacr_delta, delta_tacr >= min_tacr_delta, "pp", ">=")

    delta_latency = _coerce_float(trend.get("delta_avg_latency_ms"))
    if max_latency_increase_ms is not None:
        add_check(
            "Latency increase",
            delta_latency,
            max_latency_increase_ms,
            delta_latency <= max_latency_increase_ms,
            "ms",
            "<=",
        )

    delta_cost = _coerce_float(trend.get("delta_avg_cost_usd"))
    if max_cost_increase_usd is not None:
        add_check("Cost increase", delta_cost, max_cost_increase_usd, delta_cost <= max_cost_increase_usd, "USD", "<=")

    return {
        "enabled": True,
        "passed": not failures,
        "baseline_available": True,
        "checks": checks,
        "failures": failures,
    }


def _print_gate_status(trend: dict, gate: dict) -> bool:
    if not gate.get("enabled"):
        return True
    baseline_label = trend.get("baseline_artifact") or "baseline artifact"
    if not gate.get("baseline_available"):
        console.print(f"[bold red][GATE][FAIL][/bold red] No baseline artifact available for {baseline_label}.")
        return False

    passed = bool(gate.get("passed"))
    status = "[bold green][GATE][PASS][/bold green]" if passed else "[bold red][GATE][FAIL][/bold red]"
    console.print(f"{status} Regression gates vs {baseline_label}.")
    for check in gate.get("checks", []):
        check_status = "[green]PASS[/green]" if check.get("passed") else "[red]FAIL[/red]"
        console.print(
            f"[dim]  - {check.get('name')}: {check_status} "
            f"({check.get('actual')}{check.get('unit')} {check.get('comparator')} {check.get('threshold')}{check.get('unit')})[/dim]"
        )
    if not passed:
        for failure in gate.get("failures", []):
            console.print(f"[red]  - {failure}[/red]")
    return passed


def _write_eval_artifact(
    output_dir: Path,
    source_path: Path,
    summary: dict,
    runs: list[dict],
    *,
    trend: dict,
    pack_payload: dict | None,
    policy: dict,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now_utc().replace(":", "-")
    artifact_path = output_dir / f"eval-{timestamp}.json"
    payload: dict[str, Any] = {
        "schema_version": 2,
        "generated_at": _now_utc(),
        "source": source_path.as_posix(),
        "summary": summary,
        "trend": trend,
        "runs": runs,
        "policy": policy,
    }
    if pack_payload:
        payload["benchmark_pack"] = {
            "name": str(pack_payload.get("name", "")),
            "pack_path": str(pack_payload.get("pack_path", "")),
            "runs_file": str(pack_payload.get("runs_file", "")),
            "tasks": pack_payload.get("tasks", []),
        }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest = output_dir / "latest.json"
    latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path


def _artifact_summary_rows(output_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    rolling = {
        "tacr": 0.0,
        "avg_latency_ms": 0.0,
        "avg_cost_usd": 0.0,
        "total_interventions": 0.0,
    }
    count = 0
    for artifact_path in _artifact_files(output_dir):
        payload = _load_artifact(artifact_path)
        if not isinstance(payload, dict):
            continue
        count += 1
        summary = payload.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}
        tacr = _coerce_float(summary.get("tacr"))
        latency = _coerce_float(summary.get("avg_latency_ms"))
        cost = _coerce_float(summary.get("avg_cost_usd"))
        interventions = _coerce_float(summary.get("total_interventions"))
        rolling["tacr"] += tacr
        rolling["avg_latency_ms"] += latency
        rolling["avg_cost_usd"] += cost
        rolling["total_interventions"] += interventions
        rows.append(
            {
                "artifact": artifact_path.name,
                "generated_at": str(payload.get("generated_at", "")),
                "tacr": tacr,
                "avg_latency_ms": latency,
                "avg_cost_usd": cost,
                "total_interventions": interventions,
                "rolling_tacr": rolling["tacr"] / count,
                "rolling_avg_latency_ms": rolling["avg_latency_ms"] / count,
                "rolling_avg_cost_usd": rolling["avg_cost_usd"] / count,
                "rolling_total_interventions": rolling["total_interventions"] / count,
            }
        )
    return rows, rolling


@click.group(name="eval", invoke_without_command=True)
@click.option(
    "--input",
    "input_path",
    default=".agent/evals/runs.json",
    show_default=True,
    help="Path to run records JSON (list or {runs:[...]}).",
)
@click.option(
    "--pack",
    default=None,
    help="Benchmark pack name/path. Resolves to .agent/evals/packs/<pack>.json when a name is provided.",
)
@click.option(
    "--output-dir",
    default=".agent/evals/results",
    show_default=True,
    help="Directory where eval artifacts are written.",
)
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    help="Baseline eval artifact path. Defaults to the most recent eval artifact in the output directory.",
)
@click.option(
    "--min-tacr-delta",
    default=None,
    type=float,
    help="Minimum TACR delta allowed versus the baseline artifact.",
)
@click.option(
    "--max-latency-increase-ms",
    default=None,
    type=float,
    help="Maximum allowed average latency increase versus the baseline artifact.",
)
@click.option(
    "--max-cost-increase-usd",
    default=None,
    type=float,
    help="Maximum allowed average cost increase versus the baseline artifact.",
)
@click.option(
    "--no-ci-policy",
    is_flag=True,
    default=False,
    help="Disable automatic CI policy enforcement even when CI=true.",
)
@click.option(
    "--auto-evolve",
    is_flag=True,
    default=False,
    help="Trigger skill repair analysis on evaluation regression.",
)
def eval_command(
    input_path: str,
    pack: str | None,
    output_dir: str,
    baseline_path: str | None,
    min_tacr_delta: float | None,
    max_latency_increase_ms: float | None,
    max_cost_increase_usd: float | None,
    no_ci_policy: bool,
    auto_evolve: bool,
):
    """Summarize run metrics and persist an eval artifact."""
    ctx = click.get_current_context()
    if ctx.invoked_subcommand:
        return
    return _run_eval(
        input_path,
        pack,
        output_dir,
        baseline_path=baseline_path,
        min_tacr_delta=min_tacr_delta,
        max_latency_increase_ms=max_latency_increase_ms,
        max_cost_increase_usd=max_cost_increase_usd,
        no_ci_policy=no_ci_policy,
        auto_evolve=auto_evolve,
    )


def _run_eval(
    input_path: str,
    pack: str | None,
    output_dir: str,
    *,
    baseline_path: str | None = None,
    min_tacr_delta: float | None = None,
    max_latency_increase_ms: float | None = None,
    max_cost_increase_usd: float | None = None,
    no_ci_policy: bool = False,
    auto_evolve: bool = False,
):
    """Internal run implementation used by top-level and subcommand modes."""
    cwd = Path.cwd()
    output_path = cwd / output_dir
    policy_resolution = _resolve_eval_policy(
        cwd,
        pack=pack,
        min_tacr_delta=min_tacr_delta,
        max_latency_increase_ms=max_latency_increase_ms,
        max_cost_increase_usd=max_cost_increase_usd,
        no_ci_policy=no_ci_policy,
    )
    pack_payload = _load_pack(cwd, policy_resolution["pack"])
    source_path = _resolve_runs_source(cwd, input_path, pack_payload)
    runs = _load_runs(source_path)
    summary = _summarize_runs(runs, pack_payload=pack_payload)
    baseline_payload, baseline_label = _resolve_baseline_artifact(cwd, output_path, baseline_path)
    trend = _trend_from_payload(summary, baseline_payload, baseline_label) if baseline_path else _trend_from_previous(output_path, summary)
    artifact_path = _write_eval_artifact(
        output_path,
        source_path,
        summary,
        runs,
        trend=trend,
        pack_payload=pack_payload,
        policy=policy_resolution["policy"]
        | {
            "effective_pack": policy_resolution["pack"],
            "effective_thresholds": policy_resolution["thresholds"],
        },
    )

    console.print("[bold cyan]Skillsmith Eval[/bold cyan]")
    source_line = f"[dim]Source: {source_path.as_posix()} | Runs: {summary['total_runs']}"
    if pack_payload:
        pack_name = summary.get("benchmark_pack", {}).get("pack_name", "pack")
        source_line += f" | Pack: {pack_name}"
    source_line += "[/dim]"
    console.print(source_line)

    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("TACR", f"{summary['tacr']}%")
    table.add_row("Successful runs", str(summary["successful_runs"]))
    table.add_row("Total runs", str(summary["total_runs"]))
    table.add_row("Avg latency (ms)", str(summary["avg_latency_ms"]))
    table.add_row("Avg cost (USD)", str(summary["avg_cost_usd"]))
    table.add_row("Total interventions", str(summary["total_interventions"]))
    pack_summary = summary.get("benchmark_pack")
    if isinstance(pack_summary, dict):
        table.add_row("Pack tasks", str(pack_summary.get("total_tasks", 0)))
        table.add_row("Tasks with runs", str(pack_summary.get("tasks_with_runs", 0)))
    console.print(table)

    if trend.get("available"):
        console.print(
            "[dim]Trend vs "
            f"{trend.get('baseline_artifact')}: "
            f"Delta TACR {trend.get('delta_tacr')}pp, "
            f"Delta latency {trend.get('delta_avg_latency_ms')}ms, "
            f"Delta cost ${trend.get('delta_avg_cost_usd')}[/dim]"
        )
    else:
        console.print("[dim]Trend: no previous artifact available.[/dim]")

    console.print(f"[green][OK][/green] Wrote eval artifact: {artifact_path.as_posix()}")
    gate = _evaluate_gate(
        trend,
        min_tacr_delta=policy_resolution["thresholds"].get("min_tacr_delta"),
        max_latency_increase_ms=policy_resolution["thresholds"].get("max_latency_increase_ms"),
        max_cost_increase_usd=policy_resolution["thresholds"].get("max_cost_increase_usd"),
    )
    if gate.get("enabled"):
        passed = _print_gate_status(trend, gate)
        if not passed:
            # TRIGGER: Eval-to-Evolve Bridge (Phase 3.5)
            if auto_evolve:
                _trigger_auto_evolution(cwd, summary, pack_payload)
            
            click.get_current_context().exit(1)


def _trigger_auto_evolution(cwd: Path, summary: dict, pack_payload: dict | None) -> None:
    """Invokes the Evolution Engine to propose repairs for degraded skills."""
    from ..services.evolution import EvolutionEngine
    
    console.print("\n[bold yellow]Eval-to-Evolve Bridge:[/bold yellow] Regression detected. Analyzing skills for repair...")
    engine = EvolutionEngine(cwd)
    
    # Use centralized trigger logic
    packets = engine.trigger_evolution_from_metrics(summary)
    
    if not packets:
        console.print("[dim]No specific skill degradation patterns identified for auto-repair.[/dim]")
    else:
        for packet in packets:
            console.print(f"  [cyan][EVOLVE][/cyan] Repair packet generated: {packet.name}")


def _get_output_dir_from_context(default: str) -> str:
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.parent:
        output_dir = ctx.parent.params.get("output_dir")
        if isinstance(output_dir, str) and output_dir.strip():
            return output_dir
    return default


@eval_command.command("run")
@click.option(
    "--input",
    "input_path",
    default=".agent/evals/runs.json",
    show_default=True,
    help="Path to run records JSON (list or {runs:[...]}).",
)
@click.option(
    "--pack",
    default=None,
    help="Benchmark pack name/path. Resolves to .agent/evals/packs/<pack>.json when a name is provided.",
)
@click.option(
    "--output-dir",
    default=".agent/evals/results",
    show_default=True,
    help="Directory where eval artifacts are written.",
)
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    help="Baseline eval artifact path. Defaults to the most recent eval artifact in the output directory.",
)
@click.option(
    "--min-tacr-delta",
    default=None,
    type=float,
    help="Minimum TACR delta allowed versus the baseline artifact.",
)
@click.option(
    "--max-latency-increase-ms",
    default=None,
    type=float,
    help="Maximum allowed average latency increase versus the baseline artifact.",
)
@click.option(
    "--max-cost-increase-usd",
    default=None,
    type=float,
    help="Maximum allowed average cost increase versus the baseline artifact.",
)
@click.option(
    "--no-ci-policy",
    is_flag=True,
    default=False,
    help="Disable automatic CI policy enforcement even when CI=true.",
)
@click.option(
    "--auto-evolve",
    is_flag=True,
    default=False,
    help="Trigger skill repair analysis on evaluation regression.",
)
def eval_run_command(
    input_path: str,
    pack: str | None,
    output_dir: str,
    baseline_path: str | None,
    min_tacr_delta: float | None,
    max_latency_increase_ms: float | None,
    max_cost_increase_usd: float | None,
    no_ci_policy: bool,
    auto_evolve: bool,
):
    """Run evaluation and write an artifact."""
    _run_eval(
        input_path,
        pack,
        output_dir,
        baseline_path=baseline_path,
        min_tacr_delta=min_tacr_delta,
        max_latency_increase_ms=max_latency_increase_ms,
        max_cost_increase_usd=max_cost_increase_usd,
        no_ci_policy=no_ci_policy,
        auto_evolve=auto_evolve,
    )


@eval_command.command("packs")
def eval_packs_command():
    """List built-in benchmark packs."""
    cwd = Path.cwd()
    policy_state = _load_policy_state(cwd)
    default_pack = policy_state.get("default_pack")
    pack_specs = _builtin_pack_specs()

    console.print("[bold cyan]Skillsmith Eval Packs[/bold cyan]")
    if not pack_specs:
        console.print("[dim]No built-in benchmark packs available.[/dim]")
        return

    table = Table(box=None)
    table.add_column("Pack", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Tasks", style="white", justify="right")
    table.add_column("Default", style="yellow")
    table.add_column("Description", style="white")
    for pack in pack_specs:
        table.add_row(
            pack["name"],
            "built-in",
            str(pack["task_count"]),
            "yes" if pack["name"] == default_pack else "",
            pack["description"],
        )
    console.print(table)


@eval_command.command("dashboard")
def eval_dashboard_command():
    """Show rolling metrics across eval artifacts."""
    cwd = Path.cwd()
    output_dir = _get_output_dir_from_context(".agent/evals/results")
    output_path = cwd / output_dir
    rows, _ = _artifact_summary_rows(output_path)

    console.print("[bold cyan]Skillsmith Eval Dashboard[/bold cyan]")
    if not rows:
        console.print("[dim]No eval artifacts available.[/dim]")
        return

    latest = rows[-1]
    console.print(
        "[dim]"
        f"Artifacts: {len(rows)} | Latest: {latest['artifact']} | "
        f"Latest TACR: {latest['tacr']:.2f}% | "
        f"Rolling TACR: {latest['rolling_tacr']:.2f}%"
        "[/dim]"
    )

    table = Table(box=None)
    table.add_column("Artifact", style="cyan")
    table.add_column("TACR", style="white", justify="right")
    table.add_column("Latency", style="white", justify="right")
    table.add_column("Cost", style="white", justify="right")
    table.add_column("Interventions", style="white", justify="right")
    table.add_column("Rolling TACR", style="green", justify="right")
    table.add_column("Rolling Latency", style="green", justify="right")
    table.add_column("Rolling Cost", style="green", justify="right")
    table.add_column("Rolling Interventions", style="green", justify="right")
    for row in rows:
        table.add_row(
            row["artifact"],
            f"{row['tacr']:.2f}%",
            f"{row['avg_latency_ms']:.2f}",
            f"{row['avg_cost_usd']:.4f}",
            f"{row['total_interventions']:.2f}",
            f"{row['rolling_tacr']:.2f}%",
            f"{row['rolling_avg_latency_ms']:.2f}",
            f"{row['rolling_avg_cost_usd']:.4f}",
            f"{row['rolling_total_interventions']:.2f}",
        )
    console.print(table)


@eval_command.command("compare")
@click.option(
    "--baseline",
    "baseline_path",
    required=True,
    help="Baseline eval artifact path.",
)
@click.option(
    "--candidate",
    "candidate_path",
    required=True,
    help="Candidate eval artifact path.",
)
@click.option(
    "--min-tacr-delta",
    default=None,
    type=float,
    help="Minimum TACR delta allowed versus the baseline artifact.",
)
@click.option(
    "--max-latency-increase-ms",
    default=None,
    type=float,
    help="Maximum allowed average latency increase versus the baseline artifact.",
)
@click.option(
    "--max-cost-increase-usd",
    default=None,
    type=float,
    help="Maximum allowed average cost increase versus the baseline artifact.",
)
@click.option(
    "--no-ci-policy",
    is_flag=True,
    default=False,
    help="Disable automatic CI policy enforcement even when CI=true.",
)
@click.option(
    "--auto-evolve",
    is_flag=True,
    default=False,
    help="Trigger skill repair analysis on evaluation regression.",
)
def eval_compare_command(
    baseline_path: str,
    candidate_path: str,
    min_tacr_delta: float | None,
    max_latency_increase_ms: float | None,
    max_cost_increase_usd: float | None,
    no_ci_policy: bool,
    auto_evolve: bool,
):
    """Compare two eval artifacts and print deltas."""
    baseline_file = Path(baseline_path)
    candidate_file = Path(candidate_path)
    if not baseline_file.is_absolute():
        baseline_file = Path.cwd() / baseline_file
    if not candidate_file.is_absolute():
        candidate_file = Path.cwd() / candidate_file
    baseline_payload = _load_artifact(baseline_file)
    candidate_payload = _load_artifact(candidate_file)
    if not isinstance(baseline_payload, dict) or not isinstance(candidate_payload, dict):
        raise click.ClickException("baseline/candidate must be valid eval artifact JSON files")
    candidate_summary = candidate_payload.get("summary", {}) if isinstance(candidate_payload.get("summary", {}), dict) else {}
    trend = _trend_from_payload(candidate_summary, baseline_payload, baseline_file.as_posix())
    policy_resolution = _resolve_eval_policy(
        Path.cwd(),
        pack=None,
        min_tacr_delta=min_tacr_delta,
        max_latency_increase_ms=max_latency_increase_ms,
        max_cost_increase_usd=max_cost_increase_usd,
        no_ci_policy=no_ci_policy,
    )
    delta_tacr = trend.get("delta_tacr", 0.0)
    delta_latency = trend.get("delta_avg_latency_ms", 0.0)
    delta_cost = trend.get("delta_avg_cost_usd", 0.0)
    console.print("[bold cyan]Skillsmith Eval Compare[/bold cyan]")
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Baseline", baseline_file.as_posix())
    table.add_row("Candidate", candidate_file.as_posix())
    table.add_row("Delta TACR (pp)", str(delta_tacr))
    table.add_row("Delta latency (ms)", str(delta_latency))
    table.add_row("Delta cost (USD)", str(delta_cost))
    console.print(table)
    gate = _evaluate_gate(
        trend,
        min_tacr_delta=policy_resolution["thresholds"].get("min_tacr_delta"),
        max_latency_increase_ms=policy_resolution["thresholds"].get("max_latency_increase_ms"),
        max_cost_increase_usd=policy_resolution["thresholds"].get("max_cost_increase_usd"),
    )
    if gate.get("enabled"):
        passed = _print_gate_status(trend, gate)
        if not passed:
            click.get_current_context().exit(1)
