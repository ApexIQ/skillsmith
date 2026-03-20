from __future__ import annotations

import datetime
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from . import console
from .lockfile import _timestamp_to_string

CONTEXT_INDEX_NAME = "index.json"
QUERY_POLICY_NAME = "query_policy.json"
TRACE_DIR_NAME = "traces"
DEFAULT_QUERY_TIER = "l0"
TIER_ORDER = ("l0", "l1", "l2")
TIER_DEPTHS = {"l0": 1, "l1": 2, "l2": 3}
KEY_PROJECT_FILES = [
    "AGENTS.md",
    ".agent/PROJECT.md",
    ".agent/ROADMAP.md",
    ".agent/STATE.md",
    ".agent/project_profile.yaml",
    ".agent/context/project-context.md",
    "skills.lock.json",
    "README.md",
    "pyproject.toml",
    "docs/current_vs_expected_task_list.md",
    "src/skillsmith/cli.py",
    "src/skillsmith/commands/rendering.py",
]
SNIPPET_LIMIT = 240
TIER_SNIPPET_LIMITS = {
    "l0": SNIPPET_LIMIT,
    "l1": 480,
    "l2": 960,
}
DEFAULT_QUERY_WEIGHTS = {
    "freshness": 1.0,
    "path_priority": 1.0,
    "lexical": 1.0,
    "semantic": 0.0,
}
DEFAULT_RERANK_POLICY = {
    "enabled": False,
    "window": 5,
    "weights": {
        "freshness": 0.0,
        "path_priority": 0.0,
        "lexical": 0.25,
        "semantic": 1.0,
    },
}
PATH_GROUP_RULES = (
    (
        "agent-core",
        (
            "AGENTS.md",
            ".agent/PROJECT.md",
            ".agent/ROADMAP.md",
            ".agent/STATE.md",
            ".agent/project_profile.yaml",
            ".agent/context/project-context.md",
        ),
    ),
    (
        "workflow",
        (
            ".agent/workflows/",
            ".claude/",
            ".windsurf/",
            ".zencoder/",
        ),
    ),
    ("source", ("src/",)),
    ("tests", ("tests/",)),
    ("docs", ("docs/", "README.md")),
    ("config", ("pyproject.toml", "uv.lock", "requirements", "setup.cfg", "setup.py")),
)
PATH_GROUP_POLICIES = {
    "agent-core": {"preferred_tier": "l2", "compaction_mode": "preserve"},
    "workflow": {"preferred_tier": "l2", "compaction_mode": "preserve"},
    "source": {"preferred_tier": "l1", "compaction_mode": "retain"},
    "tests": {"preferred_tier": "l1", "compaction_mode": "retain"},
    "docs": {"preferred_tier": "l0", "compaction_mode": "compact"},
    "config": {"preferred_tier": "l0", "compaction_mode": "compact"},
    "other": {"preferred_tier": "l0", "compaction_mode": "compact"},
}
DEFAULT_BUDGET_DEPTH_BY_TOKENS = (
    (1200, 1),
    (2400, 2),
)


def _context_index_path(cwd: Path) -> Path:
    return cwd / ".agent" / "context" / CONTEXT_INDEX_NAME


def _context_trace_dir(cwd: Path) -> Path:
    return cwd / ".agent" / "context" / TRACE_DIR_NAME


def _query_policy_path(cwd: Path) -> Path:
    return cwd / ".agent" / "context" / QUERY_POLICY_NAME


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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


def _coerce_optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _slugify_trace_component(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "trace"
    slug = "".join(char if char.isalnum() else "-" for char in text)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "trace"


def _depth_for_tier(tier: str) -> int:
    return TIER_DEPTHS.get(_normalize_tier(tier), TIER_DEPTHS[DEFAULT_QUERY_TIER])


def _tier_for_depth(depth: int | None) -> str:
    resolved_depth = max(1, min(len(TIER_ORDER), _coerce_int(depth, len(TIER_ORDER))))
    return TIER_ORDER[resolved_depth - 1]


def _normalize_retrieval_depth(depth: Any, *, default: int = len(TIER_ORDER)) -> int:
    try:
        normalized = int(depth)
    except (TypeError, ValueError):
        normalized = default
    return max(1, min(len(TIER_ORDER), normalized))


def _coerce_budget_payload(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, (int, float)):
        return {"tokens": int(raw)}
    if isinstance(raw, Path):
        payload = _load_json(raw)
        return dict(payload) if isinstance(payload, dict) else None
    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    candidate = Path(text)
    if candidate.exists() and candidate.is_file():
        payload = _load_json(candidate)
        return dict(payload) if isinstance(payload, dict) else None

    try:
        payload = json.loads(text)
    except Exception:
        if text.isdigit():
            return {"tokens": int(text)}
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, (int, float)):
        return {"tokens": int(payload)}
    return None


def _budget_tokens(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("tokens", "budget_tokens", "max_tokens", "context_tokens"):
        value = _coerce_optional_int(payload.get(key))
        if value is not None:
            return max(0, value)
    return None


def _budget_depth(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("depth", "tier_depth", "retrieval_depth"):
        value = _coerce_optional_int(payload.get(key))
        if value is not None:
            return _normalize_retrieval_depth(value)
    tier = payload.get("tier")
    if tier is not None:
        try:
            return _depth_for_tier(str(tier))
        except ValueError:
            return None
    return None


def _budget_limit(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("limit", "max_results", "candidate_limit"):
        value = _coerce_optional_int(payload.get(key))
        if value is not None:
            return max(0, value)
    return None


def _path_group_for_relative_path(relative_path: str) -> str:
    for group_name, prefixes in PATH_GROUP_RULES:
        for prefix in prefixes:
            if relative_path == prefix or relative_path.startswith(prefix):
                return group_name
    return "other"


def _path_group_metadata(relative_paths: list[str]) -> tuple[list[dict], dict]:
    grouped: dict[str, list[str]] = {group_name: [] for group_name, _ in PATH_GROUP_RULES}
    grouped.setdefault("other", [])
    for relative_path in relative_paths:
        group_name = _path_group_for_relative_path(relative_path)
        grouped.setdefault(group_name, []).append(relative_path)

    path_groups: list[dict] = []
    for priority_rank, (group_name, _) in enumerate(PATH_GROUP_RULES, start=1):
        paths = sorted(grouped.get(group_name, []))
        if not paths:
            continue
        policy = PATH_GROUP_POLICIES.get(group_name, PATH_GROUP_POLICIES["other"])
        path_groups.append(
            {
                "name": group_name,
                "priority_rank": priority_rank,
                "file_count": len(paths),
                "paths": paths,
                "compaction_hint": {
                    "compaction_mode": policy["compaction_mode"],
                    "preferred_tier": policy["preferred_tier"],
                    "priority_rank": priority_rank,
                },
            }
        )

    other_paths = sorted(grouped.get("other", []))
    if other_paths:
        policy = PATH_GROUP_POLICIES["other"]
        path_groups.append(
            {
                "name": "other",
                "priority_rank": len(PATH_GROUP_RULES) + 1,
                "file_count": len(other_paths),
                "paths": other_paths,
                "compaction_hint": {
                    "compaction_mode": policy["compaction_mode"],
                    "preferred_tier": policy["preferred_tier"],
                    "priority_rank": len(PATH_GROUP_RULES) + 1,
                },
            }
        )

    compaction_hints = {
        "preferred_group_order": [group["name"] for group in path_groups],
        "compactable_groups": [
            group["name"]
            for group in path_groups
            if group["compaction_hint"]["compaction_mode"] == "compact"
        ],
        "preferred_tier_by_group": {
            group["name"]: group["compaction_hint"]["preferred_tier"] for group in path_groups
        },
        "fallback_chain": {
            "l2": ["l2", "l1", "l0"],
            "l1": ["l1", "l0"],
            "l0": ["l0"],
        },
        "target_depth_by_budget": [
            {"max_tokens": token_cap, "depth": depth}
            for token_cap, depth in DEFAULT_BUDGET_DEPTH_BY_TOKENS
        ],
    }
    return path_groups, compaction_hints


def _enrich_context_index_payload(cwd: Path, payload: dict) -> dict:
    normalized = dict(payload)
    normalized.setdefault("version", 1)
    normalized.setdefault("generated_at", _timestamp_to_string())
    normalized.setdefault("freshness_stamp", normalized.get("generated_at", _timestamp_to_string()))
    normalized.setdefault("root", ".")
    normalized.setdefault("files", [])
    normalized["file_count"] = len(normalized.get("files", []))

    enriched_files: list[dict] = []
    relative_paths: list[str] = []
    for entry in normalized.get("files", []):
        if not isinstance(entry, dict):
            continue
        enriched = _apply_tiered_snippets(entry)
        relative_path = str(enriched.get("path", "") or "")
        enriched["path_group"] = _path_group_for_relative_path(relative_path)
        enriched["path_group_priority_rank"] = next(
            (
                priority
                for priority, (group_name, _) in enumerate(PATH_GROUP_RULES, start=1)
                if group_name == enriched["path_group"]
            ),
            len(PATH_GROUP_RULES) + 1,
        )
        relative_paths.append(relative_path)
        enriched_files.append(enriched)

    normalized["files"] = enriched_files
    path_groups, compaction_hints = _path_group_metadata(relative_paths)
    normalized["path_groups"] = path_groups
    normalized["compaction_hints"] = compaction_hints
    normalized["retrieval_trace_dir"] = _context_trace_dir(cwd).relative_to(cwd).as_posix()
    return normalized


def _compress_snippet(text: str) -> str:
    return _compress_snippet_with_limit(text, SNIPPET_LIMIT)


def _compress_snippet_with_limit(text: str, limit: int) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").splitlines() if line.strip()]
    snippet = " ".join(lines)
    snippet = " ".join(snippet.split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."


def _normalize_tier(tier: Any) -> str:
    normalized = str(tier or DEFAULT_QUERY_TIER).strip().lower()
    if normalized not in TIER_SNIPPET_LIMITS:
        raise ValueError(f"Unsupported context tier: {tier!r}")
    return normalized


def _build_tiered_snippets(text: str) -> dict[str, str]:
    return {
        tier: _compress_snippet_with_limit(text, limit)
        for tier, limit in TIER_SNIPPET_LIMITS.items()
    }


def _extract_tiered_snippets(entry: dict) -> dict[str, str]:
    tier_snippets: dict[str, str] = {}
    raw_tier_snippets = entry.get("tier_snippets")
    if isinstance(raw_tier_snippets, dict):
        for tier in TIER_SNIPPET_LIMITS:
            value = raw_tier_snippets.get(tier)
            if isinstance(value, str):
                tier_snippets[tier] = value

    for tier in TIER_SNIPPET_LIMITS:
        for key in (f"{tier}_snippet", f"snippet_{tier}"):
            value = entry.get(key)
            if isinstance(value, str):
                tier_snippets[tier] = value
                break

    compressed = entry.get("compressed_snippet")
    if isinstance(compressed, str):
        tier_snippets.setdefault("l0", compressed)

    l0_snippet = tier_snippets.get("l0") or (compressed if isinstance(compressed, str) else "")
    for tier in TIER_SNIPPET_LIMITS:
        tier_snippets.setdefault(tier, l0_snippet)

    return tier_snippets


def _apply_tiered_snippets(entry: dict) -> dict:
    tier_snippets = _extract_tiered_snippets(entry)
    normalized = dict(entry)
    normalized["tier_snippets"] = tier_snippets
    normalized["l0_snippet"] = tier_snippets["l0"]
    normalized["l1_snippet"] = tier_snippets["l1"]
    normalized["l2_snippet"] = tier_snippets["l2"]
    normalized["compressed_snippet"] = tier_snippets["l0"]
    normalized["snippet"] = tier_snippets["l0"]
    return normalized


def _selected_snippet(entry: dict, tier: str) -> str:
    tier = _normalize_tier(tier)
    tier_snippets = _extract_tiered_snippets(entry)
    return tier_snippets.get(tier, tier_snippets["l0"])


def _freshness_stamp(path: Path) -> tuple[str, float]:
    modified = datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    age_seconds = max(0.0, (now - modified).total_seconds())
    return _timestamp_to_string(modified), age_seconds


def _freshness_score(age_seconds: float) -> int:
    if age_seconds <= 0:
        return 100
    days = age_seconds / 86400
    score = 100 - int(days * 5)
    return max(0, min(100, score))


def _path_priority_score(index: int) -> int:
    return max(0, 100 - (index * 8))


def _tokenize(text: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if part}


def _feature_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in sorted(_tokenize(text)):
        terms.append(f"tok:{token}")
        padded = f"^{token}$"
        if len(padded) <= 3:
            terms.append(f"tri:{padded}")
            continue
        for index in range(len(padded) - 2):
            terms.append(f"tri:{padded[index:index + 3]}")
    return terms


@lru_cache(maxsize=8192)
def _hashed_feature_vector(feature: str, dimensions: int) -> tuple[float, ...]:
    digest = hashlib.sha256(f"{dimensions}:{feature}".encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append((byte / 127.5) - 1.0)
    return tuple(values)


def _vectorize_text(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for feature in _feature_terms(text):
        feature_vector = _hashed_feature_vector(feature, dimensions)
        for index, value in enumerate(feature_vector):
            vector[index] += value
    return vector


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(l_value * r_value for l_value, r_value in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _extract_weight_map(payload: dict | None) -> dict[str, float]:
    weights = dict(DEFAULT_QUERY_WEIGHTS)
    if not isinstance(payload, dict):
        return weights

    source = payload.get("weights")
    if not isinstance(source, dict):
        source = payload

    for key in weights:
        if key in source:
            weights[key] = _coerce_float(source.get(key), weights[key])
    return weights


def _extract_semantic_policy(payload: dict | None) -> dict[str, Any]:
    semantic_payload: dict[str, Any] = {}
    if isinstance(payload, dict):
        candidate = payload.get("semantic")
        if isinstance(candidate, dict):
            semantic_payload = candidate
        elif "semantic_hint" in payload:
            semantic_payload = {"enabled": payload.get("semantic_hint")}
        elif "semantic" in payload:
            semantic_payload = {"enabled": payload.get("semantic")}

    return {
        "enabled": _coerce_bool(semantic_payload.get("enabled"), False),
        "dimensions": max(4, _coerce_int(semantic_payload.get("dimensions"), 16)),
    }


def _extract_rerank_policy(payload: dict | None) -> dict[str, Any]:
    rerank_payload: dict[str, Any] = {}
    if isinstance(payload, dict):
        candidate = payload.get("rerank")
        if isinstance(candidate, dict):
            rerank_payload = candidate
        elif "rerank" in payload:
            rerank_payload = {"enabled": payload.get("rerank")}

    weights = dict(DEFAULT_RERANK_POLICY["weights"])
    source = rerank_payload.get("weights")
    if not isinstance(source, dict):
        source = rerank_payload
    for key in weights:
        if key in source:
            weights[key] = _coerce_float(source.get(key), weights[key])

    return {
        "enabled": _coerce_bool(rerank_payload.get("enabled"), False),
        "window": max(1, _coerce_int(rerank_payload.get("window"), DEFAULT_RERANK_POLICY["window"])),
        "weights": weights,
    }


def _load_query_policy(cwd: Path) -> dict:
    path = _query_policy_path(cwd)
    payload = _load_json(path)
    if not isinstance(payload, dict):
        payload = {}
    return {
        "source": path.as_posix() if path.exists() else "",
        "weights": _extract_weight_map(payload),
        "semantic": _extract_semantic_policy(payload),
        "rerank": _extract_rerank_policy(payload),
    }


def _parse_weights_override(raw: str | None) -> dict[str, float] | None:
    return _coerce_weights_override(raw)


def _coerce_weights_override(raw: Any) -> dict[str, float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _extract_weight_map(raw)
    if isinstance(raw, Path):
        payload = _load_json(raw)
        if isinstance(payload, dict):
            return _extract_weight_map(payload)
        raise ValueError("Weights file must contain a JSON object.")
    if not isinstance(raw, str):
        raise ValueError("Weights must be a JSON object, path, or string.")

    text = raw.strip()
    if not text:
        return None

    candidate = Path(text)
    if candidate.exists() and candidate.is_file():
        payload = _load_json(candidate)
        if isinstance(payload, dict):
            return _extract_weight_map(payload)
        raise ValueError("Weights file must contain a JSON object.")

    try:
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError("Weights must be a JSON object or a path to a JSON file.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Weights must be a JSON object or a path to a JSON file.")
    return _extract_weight_map(payload)


def _build_project_file_entry(cwd: Path, path: Path, *, priority_index: int) -> dict:
    stamp, age_seconds = _freshness_stamp(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    tier_snippets = _build_tiered_snippets(text)
    return {
        "path": path.relative_to(cwd).as_posix(),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "freshness_stamp": stamp,
        "age_seconds": round(age_seconds, 2),
        "freshness_score": _freshness_score(age_seconds),
        "path_priority_rank": priority_index + 1,
        "path_priority_score": _path_priority_score(priority_index),
        "compressed_snippet": tier_snippets["l0"],
        "tier_snippets": tier_snippets,
        "l0_snippet": tier_snippets["l0"],
        "l1_snippet": tier_snippets["l1"],
        "l2_snippet": tier_snippets["l2"],
    }


def _project_file_entries(cwd: Path) -> list[dict]:
    entries: list[dict] = []
    for priority_index, relative in enumerate(KEY_PROJECT_FILES):
        path = cwd / relative
        if path == _context_index_path(cwd):
            continue
        if not path.exists() or not path.is_file():
            continue
        entries.append(_build_project_file_entry(cwd, path, priority_index=priority_index))
    return entries


def build_context_index(cwd: Path) -> dict:
    generated_at = _timestamp_to_string()
    files = _project_file_entries(cwd)
    payload = {
        "version": 1,
        "generated_at": generated_at,
        "freshness_stamp": generated_at,
        "root": ".",
        "file_count": len(files),
        "files": files,
    }
    return _enrich_context_index_payload(cwd, payload)


def _write_context_index(cwd: Path, payload: dict) -> Path:
    path = _context_index_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _load_context_index(cwd: Path) -> dict:
    path = _context_index_path(cwd)
    if not path.exists():
        payload = build_context_index(cwd)
        _write_context_index(cwd, payload)
        return payload
    payload = _load_json(path)
    if not isinstance(payload, dict):
        payload = build_context_index(cwd)
        _write_context_index(cwd, payload)
        return payload
    normalized = _enrich_context_index_payload(cwd, payload)
    if normalized != payload:
        _write_context_index(cwd, normalized)
    return normalized


def _query_lexical_score(query: str, candidate_text: str) -> tuple[int, list[str]]:
    query_tokens = _tokenize(query)
    candidate_tokens = _tokenize(candidate_text)
    matched_terms = sorted(query_tokens & candidate_tokens)
    lexical_score = min(100, len(matched_terms) * 25)
    if query.strip() and query.lower().strip() in candidate_text.lower():
        lexical_score += 10
    if query_tokens and matched_terms:
        lexical_score += 5
    return min(100, lexical_score), matched_terms


def _semantic_hint_score(query: str, candidate_text: str, dimensions: int) -> int:
    if not query.strip():
        return 0
    if not candidate_text.strip():
        return 0
    query_vector = _vectorize_text(query, dimensions)
    candidate_vector = _vectorize_text(candidate_text, dimensions)
    similarity = _cosine_similarity(query_vector, candidate_vector)
    if similarity <= 0:
        return 0
    return max(0, min(100, int(round(similarity * 100))))


def _weighted_score(components: dict[str, int], weights: dict[str, float]) -> int:
    total = 0.0
    for key, value in components.items():
        total += value * _coerce_float(weights.get(key), 0.0)
    return int(round(total))


def resolve_context_retrieval_plan(
    cwd: Path,
    *,
    tier: str | None = None,
    depth: int | None = None,
    budget: Any = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Resolve the retrieval tier/depth fallback policy for the current project."""

    payload = _load_context_index(cwd)
    budget_payload = _coerce_budget_payload(budget)
    requested_tier = None
    if tier is not None:
        try:
            requested_tier = _normalize_tier(tier)
        except ValueError:
            requested_tier = None
    requested_depth = _normalize_retrieval_depth(depth) if depth is not None else None
    budget_tokens = _budget_tokens(budget_payload)
    budget_depth = _budget_depth(budget_payload)
    budget_limit = _budget_limit(budget_payload)
    budget_limit_from_payload = budget_limit is not None
    if budget_limit is None and limit is not None:
        budget_limit = max(0, _coerce_int(limit, 0))

    depth_from_budget = budget_depth
    if depth_from_budget is None and budget_tokens is not None:
        depth_from_budget = len(TIER_ORDER)
        for token_cap, resolved_depth in DEFAULT_BUDGET_DEPTH_BY_TOKENS:
            if budget_tokens <= token_cap:
                depth_from_budget = resolved_depth
                break

    resolved_depth = requested_depth or depth_from_budget or len(TIER_ORDER)
    resolved_depth = max(1, min(len(TIER_ORDER), resolved_depth))
    if requested_tier is not None:
        requested_tier_depth = _depth_for_tier(requested_tier)
        resolved_depth = min(resolved_depth, requested_tier_depth) if depth_from_budget is not None else max(
            resolved_depth, requested_tier_depth
        )

    if budget_limit_from_payload and budget_limit is not None and budget_limit > 0:
        if budget_limit <= 2:
            resolved_depth = min(resolved_depth, 1)
        elif budget_limit <= 4:
            resolved_depth = min(resolved_depth, 2)

    resolved_tier = requested_tier or _tier_for_depth(resolved_depth)
    if _depth_for_tier(resolved_tier) > resolved_depth:
        resolved_tier = _tier_for_depth(resolved_depth)

    fallback_chain = [resolved_tier]
    if requested_tier and requested_tier not in fallback_chain:
        fallback_chain.insert(0, requested_tier)
    if resolved_tier != "l0" and "l0" not in fallback_chain:
        fallback_chain.append("l0")

    path_groups = payload.get("path_groups", [])
    if not isinstance(path_groups, list):
        path_groups = []
    compaction_hints = payload.get("compaction_hints", {})
    if not isinstance(compaction_hints, dict):
        compaction_hints = {}

    return {
        "requested": {
            "tier": requested_tier or DEFAULT_QUERY_TIER,
            "depth": requested_depth or _depth_for_tier(requested_tier or DEFAULT_QUERY_TIER),
            "limit": budget_limit or limit,
        },
        "budget": {
            "raw": budget_payload or {},
            "tokens": budget_tokens,
            "depth": budget_depth,
            "limit": budget_limit,
        },
        "resolved": {
            "tier": resolved_tier,
            "depth": resolved_depth,
            "tier_depth": _depth_for_tier(resolved_tier),
        },
        "fallbacks": fallback_chain,
        "path_groups": path_groups,
        "compaction_hints": compaction_hints,
        "context_index": {
            "file_count": int(payload.get("file_count", len(payload.get("files", []))) or 0),
            "retrieval_trace_dir": payload.get("retrieval_trace_dir", ".agent/context/traces"),
        },
    }


def _trace_candidate_summary(candidate: dict) -> dict:
    summary = {
        "path": candidate.get("path", ""),
        "score": candidate.get("score", 0),
        "base_score": candidate.get("base_score", candidate.get("score", 0)),
        "retrieval_tier": candidate.get("retrieval_tier", DEFAULT_QUERY_TIER),
        "path_group": candidate.get("path_group", "other"),
        "matched_terms": candidate.get("matched_terms", []),
    }
    if candidate.get("rerank_score") is not None:
        summary["rerank_score"] = candidate.get("rerank_score")
    return summary


def build_context_retrieval_trace(
    cwd: Path,
    *,
    source: str,
    query: str | None = None,
    goal: str | None = None,
    tier: str | None = None,
    depth: int | None = None,
    budget: Any = None,
    limit: int | None = None,
    candidates: list[dict] | None = None,
    selection: dict | None = None,
    metadata: dict | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a serializable retrieval trace for compose/autonomous flows."""

    plan = resolve_context_retrieval_plan(cwd, tier=tier, depth=depth, budget=budget, limit=limit)
    candidate_summaries = []
    for candidate in (candidates or []):
        if isinstance(candidate, dict):
            candidate_summaries.append(_trace_candidate_summary(candidate))

    request = {
        "source": source,
        "query": query,
        "goal": goal,
        "tier": tier,
        "depth": depth,
        "limit": limit,
    }
    if selection is None:
        selection = {}
    if metadata is None:
        metadata = {}
    if notes is None:
        notes = []

    trace = {
        "version": 1,
        "generated_at": _timestamp_to_string(),
        "source": source,
        "query": query,
        "goal": goal,
        "tier": plan["resolved"]["tier"],
        "retrieval_tier": plan["resolved"]["tier"],
        "request": request,
        "plan": plan,
        "selection": selection,
        "candidates": candidate_summaries,
        "metadata": metadata,
        "notes": notes,
    }
    trace["trace_id"] = _trace_id_for_payload(trace)
    trace["trace_path"] = _context_trace_dir(cwd).joinpath(f"{trace['trace_id']}.json").relative_to(cwd).as_posix()
    return trace


def _trace_id_for_payload(payload: dict) -> str:
    basis = {
        "generated_at": payload.get("generated_at", ""),
        "source": payload.get("source", ""),
        "request": payload.get("request", {}),
        "selection": payload.get("selection", {}),
    }
    digest = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()[:12]
    source = _slugify_trace_component(payload.get("source", "trace"))
    return f"{str(payload.get('generated_at', _timestamp_to_string())).replace(':', '-')}-{source}-{digest}"


def persist_context_retrieval_trace(cwd: Path, trace: dict[str, Any]) -> Path:
    """Persist a retrieval trace to `.agent/context/traces/`."""

    trace_dir = _context_trace_dir(cwd)
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_payload = dict(trace)
    trace_id = str(trace_payload.get("trace_id") or _trace_id_for_payload(trace_payload))
    trace_path = trace_dir / f"{trace_id}.json"
    trace_payload["trace_id"] = trace_id
    trace_payload["trace_path"] = trace_path.relative_to(cwd).as_posix()
    trace_path.write_text(json.dumps(trace_payload, indent=2, sort_keys=True), encoding="utf-8")
    return trace_path


def _rerank_score(entry: dict, rerank_policy: dict) -> int:
    components = {
        "freshness": int(entry.get("freshness_score", 0) or 0),
        "path_priority": int(entry.get("path_priority_score", 0) or 0),
        "lexical": int(entry.get("lexical_score", 0) or 0),
        "semantic": int(entry.get("semantic_hint_score", 0) or 0),
    }
    return _weighted_score(components, rerank_policy.get("weights", {}))


def _rank_context_entries(
    entries: list[dict],
    query: str,
    *,
    policy: dict | None = None,
    tier: str = DEFAULT_QUERY_TIER,
) -> list[dict]:
    policy = dict(policy or {})
    normalized_tier = _normalize_tier(tier)
    base_weights = _extract_weight_map(policy)
    semantic_policy = _extract_semantic_policy(policy)
    rerank_policy = _extract_rerank_policy(policy)
    semantic_enabled = semantic_policy["enabled"] or rerank_policy["enabled"] or base_weights.get("semantic", 0.0) != 0.0

    ranked: list[dict] = []
    for index, entry in enumerate(entries):
        normalized = dict(entry)
        freshness_score = int(normalized.get("freshness_score", 0) or 0)
        path_priority_score = int(normalized.get("path_priority_score", _path_priority_score(index)) or 0)
        path_group = str(normalized.get("path_group") or _path_group_for_relative_path(str(normalized.get("path", ""))))
        normalized["path_group"] = path_group
        normalized["path_group_priority_rank"] = int(
            normalized.get("path_group_priority_rank")
            or next((priority for priority, (group_name, _) in enumerate(PATH_GROUP_RULES, start=1) if group_name == path_group), len(PATH_GROUP_RULES) + 1)
        )
        normalized.setdefault(
            "compaction_hint",
            {
                "compaction_mode": PATH_GROUP_POLICIES.get(path_group, PATH_GROUP_POLICIES["other"])["compaction_mode"],
                "preferred_tier": PATH_GROUP_POLICIES.get(path_group, PATH_GROUP_POLICIES["other"])["preferred_tier"],
                "priority_rank": normalized["path_group_priority_rank"],
            },
        )
        selected_snippet = _selected_snippet(normalized, normalized_tier)
        candidate_text = f"{normalized.get('path', '')} {selected_snippet}"
        lexical_score, matched_terms = _query_lexical_score(query, candidate_text)
        semantic_hint_score = _semantic_hint_score(query, candidate_text, semantic_policy["dimensions"]) if semantic_enabled else 0
        base_components = {
            "freshness": freshness_score,
            "path_priority": path_priority_score,
            "lexical": lexical_score,
            "semantic": semantic_hint_score,
        }
        base_score = _weighted_score(base_components, base_weights)
        normalized["freshness_score"] = freshness_score
        normalized["path_priority_score"] = path_priority_score
        normalized["lexical_score"] = lexical_score
        normalized["semantic_hint_score"] = semantic_hint_score
        normalized["matched_terms"] = matched_terms
        normalized["retrieval_tier"] = normalized_tier
        normalized["selected_snippet"] = selected_snippet
        normalized["base_score"] = base_score
        normalized["score"] = base_score
        normalized["score_breakdown"] = {
            "weights": dict(base_weights),
            "base": {
                "freshness": freshness_score,
                "path_priority": path_priority_score,
                "lexical": lexical_score,
                "semantic": semantic_hint_score,
                "score": base_score,
            },
            "rerank": None,
            "final": base_score,
        }
        ranked.append(normalized)

    ranked = sorted(ranked, key=lambda item: (-item["score"], item.get("path", "")))
    if not rerank_policy["enabled"] or not ranked:
        return ranked

    rerank_window = min(len(ranked), rerank_policy["window"])
    reranked_top: list[dict] = []
    for item in ranked[:rerank_window]:
        rerank_score = _rerank_score(item, rerank_policy)
        rerank_components = {
            "freshness": item["freshness_score"],
            "path_priority": item["path_priority_score"],
            "lexical": item["lexical_score"],
            "semantic": item["semantic_hint_score"],
            "score": rerank_score,
        }
        reranked_item = dict(item)
        reranked_item["rerank_score"] = rerank_score
        reranked_item["score"] = rerank_score
        reranked_item["score_breakdown"] = {
            "weights": dict(base_weights),
            "base": item["score_breakdown"]["base"],
            "rerank": {
                "weights": dict(rerank_policy["weights"]),
                **rerank_components,
            },
            "final": rerank_score,
        }
        reranked_top.append(reranked_item)

    reranked_top = sorted(reranked_top, key=lambda item: (-item["score"], item.get("path", "")))
    remainder: list[dict] = []
    for item in ranked[rerank_window:]:
        remainder_item = dict(item)
        remainder_item["rerank_score"] = None
        remainder.append(remainder_item)
    return reranked_top + remainder


def _format_breakdown(item: dict) -> str:
    base = item.get("score_breakdown", {}).get("base", {})
    rerank = item.get("score_breakdown", {}).get("rerank")
    parts = [
        f"base={item.get('base_score', item.get('score', 0))}",
        f"freshness={base.get('freshness', 0)}",
        f"path_priority={base.get('path_priority', 0)}",
        f"lexical={base.get('lexical', 0)}",
        f"semantic={base.get('semantic', 0)}",
    ]
    if rerank:
        parts.append(f"rerank={rerank.get('score', 0)}")
    parts.append(f"final={item.get('score', 0)}")
    return " ".join(parts)


def _print_context_index_table(entries: list[dict]) -> None:
    table = Table(box=None, title="Context Index")
    table.add_column("File", style="cyan")
    table.add_column("Freshness", style="green")
    table.add_column("Path Priority", style="magenta")
    table.add_column("Snippet", style="white")
    for item in entries:
        table.add_row(
            item["path"],
            item["freshness_stamp"],
            str(item["path_priority_score"]),
            item["compressed_snippet"][:80] + ("..." if len(item["compressed_snippet"]) > 80 else ""),
        )
    if entries:
        console.print(table)
    else:
        console.print("[dim]No key project files were found to index.[/dim]")


def _print_query_table(results: list[dict], query: str) -> None:
    table = Table(title=f'Context Index Query ({len(results)}) - "{query}"')
    table.add_column("Score", style="yellow", justify="right")
    table.add_column("Base", style="green", justify="right")
    table.add_column("Freshness", style="green", justify="right")
    table.add_column("Path Priority", style="magenta", justify="right")
    table.add_column("Lexical", style="cyan", justify="right")
    table.add_column("Semantic", style="bright_cyan", justify="right")
    table.add_column("Rerank", style="bright_magenta", justify="right")
    table.add_column("File", style="white")
    table.add_column("Matched", style="blue")
    table.add_column("Snippet", style="dim")
    for item in results:
        snippet = item.get("selected_snippet", item.get("compressed_snippet", ""))
        table.add_row(
            str(item["score"]),
            str(item.get("base_score", item["score"])),
            str(item["freshness_score"]),
            str(item["path_priority_score"]),
            str(item["lexical_score"]),
            str(item.get("semantic_hint_score", 0)),
            str(item.get("rerank_score", "none")) if item.get("rerank_score") is not None else "none",
            item["path"],
            ", ".join(item["matched_terms"]) or "none",
            snippet[:80] + ("..." if len(snippet) > 80 else ""),
        )
    console.print(table)


def retrieve_context_candidates(
    cwd: Path,
    query: str,
    limit: int = 5,
    tier: str = DEFAULT_QUERY_TIER,
    weights_override: Any = None,
    *,
    budget: Any = None,
    depth: int | None = None,
) -> list[dict]:
    """Return ranked context candidates for reuse by other modules."""
    plan = resolve_context_retrieval_plan(cwd, tier=tier, depth=depth, budget=budget, limit=limit)
    normalized_tier = plan["resolved"]["tier"]
    payload = _load_context_index(cwd)
    policy = _load_query_policy(cwd)
    override = _coerce_weights_override(weights_override)
    if override is not None:
        policy = _merge_dicts(policy, {"weights": override})
    results = _rank_context_entries(payload.get("files", []), query, policy=policy, tier=normalized_tier)
    resolved_limit = plan["budget"]["limit"] or limit
    clipped = results[: max(0, int(resolved_limit))]
    for item in clipped:
        item["retrieval_plan"] = plan
        item["retrieval_tier"] = normalized_tier
        item["retrieval_depth"] = plan["resolved"]["depth"]
        item["retrieval_budget_tokens"] = plan["budget"]["tokens"]
        item["retrieval_fallbacks"] = list(plan["fallbacks"])
    return clipped[: max(0, int(limit))]


@click.group(
    name="context-index",
    help="Build and query a retrieval-friendly context index for the current project.",
    invoke_without_command=True,
)
@click.pass_context
def context_index_command(ctx):
    """Build a retrieval-friendly context index for the current project."""
    if ctx.invoked_subcommand is not None:
        return
    _run_context_index_build(Path.cwd())


def _run_context_index_build(cwd: Path) -> dict:
    payload = build_context_index(cwd)
    path = _write_context_index(cwd, payload)

    console.print("[bold cyan]Context Index[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Indexed {payload['file_count']} key project files[/dim]")
    _print_context_index_table(payload["files"])
    return payload


@context_index_command.command("build")
def context_index_build_command():
    """Build the retrieval-friendly context index."""
    _run_context_index_build(Path.cwd())


@context_index_command.command("query")
@click.argument("query")
@click.option("--limit", default=5, show_default=True, help="Maximum number of results")
@click.option(
    "--tier",
    default=DEFAULT_QUERY_TIER,
    show_default=True,
    type=click.Choice(sorted(TIER_SNIPPET_LIMITS.keys()), case_sensitive=False),
    help="Context snippet tier to use for retrieval.",
)
@click.option("--weights", default=None, help="JSON object or path to a JSON file overriding retrieval weights.")
def context_index_query_command(query, limit, tier, weights):
    """Rank indexed project files for retrieval."""
    cwd = Path.cwd()
    policy = _load_query_policy(cwd)
    try:
        normalized_tier = _normalize_tier(tier)
        weights_override = _parse_weights_override(weights)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    if weights_override is not None:
        policy = _merge_dicts(policy, {"weights": weights_override})

    results = retrieve_context_candidates(cwd, query, limit=limit, tier=normalized_tier, weights_override=weights_override)
    trace = build_context_retrieval_trace(
        cwd,
        source="context-index-query",
        query=query,
        tier=normalized_tier,
        limit=limit,
        candidates=results,
        selection={"result_paths": [item.get("path", "") for item in results]},
    )
    trace_path = persist_context_retrieval_trace(cwd, trace)

    console.print("[bold cyan]Context Index Query[/bold cyan]")
    console.print(f"[dim]Query: {query}[/dim]")
    console.print(f"[dim]Tier: {normalized_tier}[/dim]")
    console.print(f"[dim]Trace: {trace_path.relative_to(cwd).as_posix()}[/dim]")
    console.print(
        "[dim]Weights: "
        f"freshness={policy['weights']['freshness']} "
        f"path_priority={policy['weights']['path_priority']} "
        f"lexical={policy['weights']['lexical']} "
        f"semantic={policy['weights']['semantic']} "
        f"semantic_hint={'on' if policy['semantic']['enabled'] else 'off'} "
        f"rerank={'on' if policy['rerank']['enabled'] else 'off'}[/dim]"
    )
    if policy["rerank"]["enabled"]:
        console.print(f"[dim]Rerank window: {policy['rerank']['window']}[/dim]")
    if not results:
        console.print("[dim]No indexed files were available for retrieval.[/dim]")
        return
    console.print("[dim]Ranked candidates:[/dim]")
    for item in results:
        console.print(
            "[dim]- "
            f"{_format_breakdown(item)} "
            f"path={item['path']} "
            f"matched={', '.join(item['matched_terms']) or 'none'}"
            "[/dim]"
        )
    _print_query_table(results, query)
