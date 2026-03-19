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


def _context_index_path(cwd: Path) -> Path:
    return cwd / ".agent" / "context" / CONTEXT_INDEX_NAME


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


def _compress_snippet(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").splitlines() if line.strip()]
    snippet = " ".join(lines)
    snippet = " ".join(snippet.split())
    if len(snippet) <= SNIPPET_LIMIT:
        return snippet
    return snippet[: SNIPPET_LIMIT - 3].rstrip() + "..."


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
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    candidate = Path(text)
    if candidate.exists() and candidate.is_file():
        payload = _load_json(candidate)
        if isinstance(payload, dict):
            return _extract_weight_map(payload)
        raise click.BadParameter("Weights file must contain a JSON object.")

    try:
        payload = json.loads(text)
    except Exception as exc:
        raise click.BadParameter("Weights must be a JSON object or a path to a JSON file.") from exc
    if not isinstance(payload, dict):
        raise click.BadParameter("Weights must be a JSON object or a path to a JSON file.")
    return _extract_weight_map(payload)


def _build_project_file_entry(cwd: Path, path: Path, *, priority_index: int) -> dict:
    stamp, age_seconds = _freshness_stamp(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "path": path.relative_to(cwd).as_posix(),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "freshness_stamp": stamp,
        "age_seconds": round(age_seconds, 2),
        "freshness_score": _freshness_score(age_seconds),
        "path_priority_rank": priority_index + 1,
        "path_priority_score": _path_priority_score(priority_index),
        "compressed_snippet": _compress_snippet(text),
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
    return {
        "version": 1,
        "generated_at": generated_at,
        "freshness_stamp": generated_at,
        "root": ".",
        "file_count": len(files),
        "files": files,
    }


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
    payload.setdefault("files", [])
    payload.setdefault("file_count", len(payload.get("files", [])))
    return payload


def _query_lexical_score(query: str, entry: dict) -> tuple[int, list[str]]:
    query_tokens = _tokenize(query)
    candidate_text = f"{entry.get('path', '')} {entry.get('compressed_snippet', '')}"
    candidate_tokens = _tokenize(candidate_text)
    matched_terms = sorted(query_tokens & candidate_tokens)
    lexical_score = min(100, len(matched_terms) * 25)
    if query.strip() and query.lower().strip() in candidate_text.lower():
        lexical_score += 10
    if query_tokens and matched_terms:
        lexical_score += 5
    return min(100, lexical_score), matched_terms


def _semantic_hint_score(query: str, entry: dict, dimensions: int) -> int:
    if not query.strip():
        return 0
    candidate_text = f"{entry.get('path', '')} {entry.get('compressed_snippet', '')}"
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


def _rerank_score(entry: dict, rerank_policy: dict) -> int:
    components = {
        "freshness": int(entry.get("freshness_score", 0) or 0),
        "path_priority": int(entry.get("path_priority_score", 0) or 0),
        "lexical": int(entry.get("lexical_score", 0) or 0),
        "semantic": int(entry.get("semantic_hint_score", 0) or 0),
    }
    return _weighted_score(components, rerank_policy.get("weights", {}))


def _rank_context_entries(entries: list[dict], query: str, *, policy: dict | None = None) -> list[dict]:
    policy = dict(policy or {})
    base_weights = _extract_weight_map(policy)
    semantic_policy = _extract_semantic_policy(policy)
    rerank_policy = _extract_rerank_policy(policy)
    semantic_enabled = semantic_policy["enabled"] or rerank_policy["enabled"] or base_weights.get("semantic", 0.0) != 0.0

    ranked: list[dict] = []
    for index, entry in enumerate(entries):
        normalized = dict(entry)
        freshness_score = int(normalized.get("freshness_score", 0) or 0)
        path_priority_score = int(normalized.get("path_priority_score", _path_priority_score(index)) or 0)
        lexical_score, matched_terms = _query_lexical_score(query, normalized)
        semantic_hint_score = _semantic_hint_score(query, normalized, semantic_policy["dimensions"]) if semantic_enabled else 0
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
            item["compressed_snippet"][:80] + ("..." if len(item["compressed_snippet"]) > 80 else ""),
        )
    console.print(table)


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

    cwd = Path.cwd()
    payload = build_context_index(cwd)
    path = _write_context_index(cwd, payload)

    console.print("[bold cyan]Context Index[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Indexed {payload['file_count']} key project files[/dim]")
    _print_context_index_table(payload["files"])


@context_index_command.command("query")
@click.argument("query")
@click.option("--limit", default=5, show_default=True, help="Maximum number of results")
@click.option("--weights", default=None, help="JSON object or path to a JSON file overriding retrieval weights.")
def context_index_query_command(query, limit, weights):
    """Rank indexed project files for retrieval."""
    cwd = Path.cwd()
    payload = _load_context_index(cwd)
    policy = _load_query_policy(cwd)
    weights_override = _parse_weights_override(weights)
    if weights_override is not None:
        policy = _merge_dicts(policy, {"weights": weights_override})

    results = _rank_context_entries(payload.get("files", []), query, policy=policy)[: max(0, int(limit))]

    console.print("[bold cyan]Context Index Query[/bold cyan]")
    console.print(f"[dim]Query: {query}[/dim]")
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
