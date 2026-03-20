from __future__ import annotations

import copy
import csv
import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import time
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from . import TEMPLATE_DIR, sanitize_json
from .init import _infer_project_profile
from .lockfile import load_lockfile, load_trust_health, verify_lockfile_signature
from .providers import explain_recommendations_for_profile, get_profile
from .rendering import load_project_profile

AUTONOMY_ROOT = Path('.agent') / 'autonomy'
AUTONOMY_RUNS_DIR = AUTONOMY_ROOT / 'runs'
AUTONOMY_BENCHMARKS_DIR = AUTONOMY_ROOT / 'benchmarks'
AUTONOMY_RESULTS_TSV = AUTONOMY_ROOT / 'results.tsv'
AUTONOMY_LATEST_POINTER = AUTONOMY_ROOT / 'latest.json'
AUTONOMY_LESSONS_PATH = AUTONOMY_ROOT / 'lessons.json'
AUTONOMY_SNAPSHOTS_ROOT = Path('.agent') / 'autonomy_snapshots'
TEMPLATE_AUTONOMY_DIR = TEMPLATE_DIR / '.agent' / 'autonomy'
DEFAULT_BENCHMARK_PACK = 'recommendation_tasks.json'
DEFAULT_TEST_COMMAND = ('uv', 'run', 'python', '-m', 'unittest', 'discover', 'tests', '-v')
SUPPORTED_DOMAINS = {'recommend', 'recommendation'}
SESSION_SCHEMA_VERSION = 1
MATCH_THRESHOLD = 0.5
LESSON_DECAY_HALF_LIFE_DAYS = 30
LESSON_DECAY_WEIGHT = 1.0
TOKEN_STOPWORDS = {
    'a', 'an', 'and', 'best', 'for', 'of', 'on', 'or', 'practice', 'practices',
    'project', 'recommend', 'recommendation', 'recommended', 'skill', 'skills',
    'task', 'tasks', 'the', 'to', 'with', 'workflow', 'workflows',
}


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _resolve_cwd(cwd: Path | str | None) -> Path:
    return (Path(cwd) if cwd is not None else Path.cwd()).resolve()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if lowered in {'0', 'false', 'no', 'n', 'off'}:
            return False
    return default


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _tokenize(text: Any) -> list[str]:
    raw = re.sub(r'[^a-zA-Z0-9]+', ' ', str(text or '').lower())
    return [token for token in raw.split() if token and token not in TOKEN_STOPWORDS]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=str)]
    return value


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f'{path.name}.tmp-{uuid.uuid4().hex}')
    tmp_path.write_text(content, encoding='utf-8')
    tmp_path.replace(path)


def _write_json(path: Path, payload: dict) -> None:
    _atomic_write_text(path, json.dumps(_jsonable(sanitize_json(payload)), indent=2, sort_keys=True, ensure_ascii=True))


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _load_profile(cwd: Path) -> dict:
    try:
        profile = load_project_profile(cwd)
        if isinstance(profile, dict) and profile:
            return profile
    except Exception:
        pass

    profile = get_profile(cwd)
    if isinstance(profile, dict) and profile:
        return profile

    return _infer_project_profile(cwd)


def _git_command(cwd: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None


def _git_preflight(cwd: Path) -> dict:
    inside = _git_command(cwd, ['rev-parse', '--is-inside-work-tree'])
    if inside is None:
        return {'state': 'missing', 'clean': False, 'reason': 'git_not_available', 'dirty_paths': [], 'branch': '', 'commit': '', 'status': ''}
    if inside.returncode != 0:
        return {'state': 'missing', 'clean': False, 'reason': 'not_a_git_repository', 'dirty_paths': [], 'branch': '', 'commit': '', 'status': inside.stderr.strip()}

    status = _git_command(cwd, ['status', '--porcelain=v1', '--untracked-files=all'])
    branch = _git_command(cwd, ['rev-parse', '--abbrev-ref', 'HEAD'])
    commit = _git_command(cwd, ['rev-parse', '--short', 'HEAD'])
    if status is None:
        return {'state': 'error', 'clean': False, 'reason': 'git_not_available', 'dirty_paths': [], 'branch': branch.stdout.strip() if branch and branch.returncode == 0 else '', 'commit': commit.stdout.strip() if commit and commit.returncode == 0 else '', 'status': ''}

    dirty_paths: list[str] = []
    for line in status.stdout.strip().splitlines():
        line = line.rstrip()
        if not line:
            continue
        dirty_paths.append(line[3:].strip() if len(line) > 3 else line.strip())

    return {
        'state': 'clean' if not dirty_paths else 'dirty',
        'clean': not dirty_paths,
        'reason': '' if not dirty_paths else 'uncommitted_changes',
        'dirty_paths': dirty_paths,
        'branch': branch.stdout.strip() if branch and branch.returncode == 0 else '',
        'commit': commit.stdout.strip() if commit and commit.returncode == 0 else '',
        'status': status.stdout.strip(),
    }


def _resolve_benchmark_path(cwd: Path, benchmark_pack: str | Path | dict | None) -> Path | None:
    if isinstance(benchmark_pack, dict):
        return None
    if isinstance(benchmark_pack, Path) and benchmark_pack.exists():
        return benchmark_pack
    if isinstance(benchmark_pack, str) and benchmark_pack.strip():
        candidate = Path(benchmark_pack)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        direct = cwd / benchmark_pack
        if direct.exists():
            return direct
        named = benchmark_pack if benchmark_pack.endswith('.json') else f'{benchmark_pack}.json'
        local_named = cwd / AUTONOMY_BENCHMARKS_DIR / named
        if local_named.exists():
            return local_named
        template_named = TEMPLATE_AUTONOMY_DIR / 'benchmarks' / named
        if template_named.exists():
            return template_named
    local_default = cwd / AUTONOMY_BENCHMARKS_DIR / DEFAULT_BENCHMARK_PACK
    if local_default.exists():
        return local_default
    template_default = TEMPLATE_AUTONOMY_DIR / 'benchmarks' / DEFAULT_BENCHMARK_PACK
    if template_default.exists():
        return template_default
    return None


def _load_benchmark_pack(cwd: Path, benchmark_pack: str | Path | dict | None) -> dict:
    if isinstance(benchmark_pack, dict):
        payload = dict(benchmark_pack)
        pack_path = ''
    else:
        pack_path_obj = _resolve_benchmark_path(cwd, benchmark_pack)
        payload = _load_json(pack_path_obj) if pack_path_obj is not None else None
        pack_path = pack_path_obj.as_posix() if pack_path_obj is not None else ''
        if not isinstance(payload, dict):
            payload = {}

    tasks = payload.get('tasks', [])
    if not isinstance(tasks, list):
        tasks = []
    return {
        'name': str(payload.get('name', DEFAULT_BENCHMARK_PACK.replace('.json', ''))),
        'description': str(payload.get('description', '')),
        'tasks': [task for task in tasks if isinstance(task, dict)],
        'source': str(payload.get('source', '')),
        'pack_path': pack_path,
    }


def _load_session_payload(value: dict | str | Path | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get('kind') == 'latest-pointer':
            session_path = value.get('session_path')
            if isinstance(session_path, str) and session_path.strip():
                resolved = Path(session_path)
                if not resolved.is_absolute():
                    base_dir = Path(value.get('_base_dir', Path.cwd()))
                    resolved = (base_dir / resolved).resolve()
                payload = _load_json(resolved)
                if isinstance(payload, dict):
                    return payload
        return value

    path = Path(value)
    if not path.exists():
        return None
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return None
    if payload.get('kind') == 'latest-pointer':
        session_path = payload.get('session_path')
        if isinstance(session_path, str) and session_path.strip():
            resolved = Path(session_path)
            if not resolved.is_absolute():
                resolved = (path.parent / resolved).resolve()
            session_payload = _load_json(resolved)
            if isinstance(session_payload, dict):
                return session_payload
    return payload


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def _stable_json_hash(payload: Any) -> str:
    return hashlib.sha256(_stable_json_bytes(payload)).hexdigest()


def _resolve_runtime_path(cwd: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (cwd / path).resolve()
    return path


def _safe_zone_name(path: Path, cwd: Path) -> str:
    try:
        relative = path.relative_to(cwd)
    except ValueError:
        relative = Path(path.name or 'zone')
    text = relative.as_posix().strip('/').replace('/', '__')
    return text or 'zone'


def _is_unsafe_mutation_zone(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    unsafe_roots = {AUTONOMY_ROOT.resolve(), AUTONOMY_SNAPSHOTS_ROOT.resolve()}
    for unsafe_root in unsafe_roots:
        if resolved == unsafe_root:
            return True
        if unsafe_root in resolved.parents:
            return True
    return False


def _normalize_mutation_zones(cwd: Path, mutation_zones: Any) -> tuple[list[Path], list[str]]:
    if mutation_zones is None:
        return [], []
    if isinstance(mutation_zones, (str, Path)):
        raw_zones = [mutation_zones]
    else:
        raw_zones = list(mutation_zones) if isinstance(mutation_zones, Sequence) else [mutation_zones]

    zones: list[Path] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for raw_zone in raw_zones:
        path = _resolve_runtime_path(cwd, raw_zone)
        if path is None:
            continue
        key = path.as_posix()
        if key in seen:
            continue
        if _is_unsafe_mutation_zone(path):
            skipped.append(key)
            continue
        seen.add(key)
        zones.append(path)
    return zones, skipped


def _context_index_summary(cwd: Path) -> dict:
    path = cwd / '.agent' / 'context' / 'index.json'
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return {'present': False, 'path': path.as_posix(), 'version': 0, 'hash': '', 'file_count': 0}
    normalized = _stable_json_bytes(payload)
    return {
        'present': True,
        'path': path.as_posix(),
        'version': _coerce_int(payload.get('version'), 0),
        'hash': hashlib.sha256(normalized).hexdigest(),
        'file_count': _coerce_int(payload.get('file_count'), len(payload.get('files', [])) if isinstance(payload.get('files'), list) else 0),
    }


def _benchmark_summary(benchmark: dict) -> dict:
    tasks = [task for task in benchmark.get('tasks', []) if isinstance(task, dict)]
    payload = {
        'name': benchmark.get('name', ''),
        'description': benchmark.get('description', ''),
        'source': benchmark.get('source', ''),
        'pack_path': benchmark.get('pack_path', ''),
        'tasks': tasks,
    }
    return {
        'name': str(benchmark.get('name', '')),
        'description': str(benchmark.get('description', '')),
        'source': str(benchmark.get('source', '')),
        'pack_path': str(benchmark.get('pack_path', '')),
        'task_count': len(tasks),
        'task_ids': [str(task.get('id', f'task-{index + 1}')) for index, task in enumerate(tasks)],
        'hash': _stable_json_hash(payload),
    }


def _build_task_graph(session_id: str, benchmark: dict) -> dict:
    tasks = [task for task in benchmark.get('tasks', []) if isinstance(task, dict)]
    root_path = f'session/{session_id}/benchmark/{benchmark.get("name", "benchmark")}'
    nodes: list[dict] = []
    path_index: dict[str, str] = {}
    for index, task in enumerate(tasks):
        task_id = str(task.get('id', f'task-{index + 1}')).strip() or f'task-{index + 1}'
        task_path = f'{root_path}/tasks/{task_id}'
        node = {
            'id': task_id,
            'node_type': 'goal' if index == 0 else 'task',
            'title': str(task.get('title', task_id)),
            'goal': str(task.get('goal', task.get('description', task.get('title', '')))),
            'task_graph_path': task_path,
            'task_graph_parent_path': root_path,
            'task_graph_index': index,
            'expected_skills': _safe_list(task.get('expected_skills')),
        }
        path_index[task_id] = task_path
        nodes.append(node)
    return {'root_path': root_path, 'nodes': nodes, 'path_index': path_index}


def _build_evaluation_surface(session_id: str, benchmark: dict, replay_session: dict | None = None) -> dict:
    scenario = {
        'scenario_id': benchmark.get('name', 'benchmark'),
        'scenario_name': benchmark.get('name', 'benchmark'),
        'scenario_type': 'benchmark-pack',
        'description': benchmark.get('description', ''),
        'source': benchmark.get('source', ''),
        'pack_path': benchmark.get('pack_path', ''),
        'task_count': len([task for task in benchmark.get('tasks', []) if isinstance(task, dict)]),
        'task_ids': [str(task.get('id', f'task-{index + 1}')) for index, task in enumerate(benchmark.get('tasks', []) if isinstance(benchmark.get('tasks', []), list) else []) if isinstance(task, dict)],
        'session_scope': session_id,
    }
    replay = {
        'enabled': isinstance(replay_session, dict),
        'source_session_id': '',
        'source_status': '',
        'source_summary': {},
    }
    if isinstance(replay_session, dict):
        replay['source_session_id'] = str(replay_session.get('session_id', ''))
        replay['source_status'] = str(replay_session.get('status', ''))
        replay['source_summary'] = summarize_session(replay_session)
    return {'scenario': scenario, 'replay': replay}


def _build_runtime_policy(
    *,
    domain: str,
    max_iterations: int,
    max_hours: float,
    max_non_improving: int,
    score_gate: float | None,
    recommendation_limit: int,
    strict_test_command: Sequence[str] | None,
    strict_gate: bool,
    mutation_zones: list[Path],
    skipped_mutation_zones: list[str],
    max_depth: int | None,
) -> dict:
    depth_limit = max(1, _coerce_int(max_depth, recommendation_limit) if max_depth is not None else recommendation_limit)
    policy = {
        'domain': domain,
        'budget': {
            'depth_limit': depth_limit,
            'iteration_limit': max_iterations,
            'time_limit_hours': max_hours,
            'non_improving_limit': max_non_improving,
        },
        'early_stop': {
            'score_gate': score_gate,
            'enabled': True,
            'policy': 'budget-aware',
        },
        'evaluation_depth_limit': depth_limit,
        'recommendation_limit': recommendation_limit,
        'strict_gate': bool(strict_gate),
        'strict_test_command': list(strict_test_command or DEFAULT_TEST_COMMAND),
        'mutation_zones': [path.as_posix() for path in mutation_zones],
        'skipped_mutation_zones': list(skipped_mutation_zones),
    }
    policy['hash'] = _stable_json_hash(policy)
    return policy


def _build_trust_summary(cwd: Path, profile: dict) -> dict:
    trust_health = load_trust_health(cwd, profile)
    lockfile = load_lockfile(cwd)
    signature = verify_lockfile_signature(lockfile)
    revocations = trust_health.get('revocations', {}) if isinstance(trust_health.get('revocations'), dict) else {}
    transparency_log = trust_health.get('transparency_log', {}) if isinstance(trust_health.get('transparency_log'), dict) else {}
    authority = trust_health.get('authority', {}) if isinstance(trust_health.get('authority'), dict) else {}
    return {
        'available': True,
        'lockfile_signature': signature,
        'lockfile_signature_valid': bool(signature.get('valid')),
        'lockfile_signature_state': signature.get('state', ''),
        'trust_health': trust_health,
        'revocations': revocations,
        'transparency_log': transparency_log,
        'authority': authority,
        'trusted_publisher_key_ids': list(trust_health.get('trusted_publisher_key_ids', [])),
        'trusted_publisher_public_key_ids': list(trust_health.get('trusted_publisher_public_key_ids', [])),
        'revoked_key_ids': list(revocations.get('revoked_key_ids', [])),
    }


def _lesson_decay_score(first_seen_at: str, current_at: str) -> float:
    try:
        first = dt.datetime.fromisoformat(first_seen_at.replace('Z', '+00:00'))
        current = dt.datetime.fromisoformat(current_at.replace('Z', '+00:00'))
        age_days = max(0.0, (current - first).total_seconds() / 86400.0)
        if LESSON_DECAY_HALF_LIFE_DAYS <= 0:
            return LESSON_DECAY_WEIGHT
        decay = LESSON_DECAY_WEIGHT - (age_days / float(LESSON_DECAY_HALF_LIFE_DAYS))
        return round(max(0.0, decay), 4)
    except Exception:
        return LESSON_DECAY_WEIGHT


def _lesson_dedupe_key(lesson: dict) -> str:
    return _stable_json_hash({
        'kind': lesson.get('kind', ''),
        'summary': lesson.get('summary', ''),
        'recommended_action': lesson.get('recommended_action', ''),
        'task_graph_path': lesson.get('task_graph_path', ''),
        'scenario_id': lesson.get('scenario_id', ''),
    })


def _extract_lessons_from_iteration(
    *,
    session_id: str,
    iteration: dict,
    benchmark_result: dict,
    trust_summary: dict,
    session_manifest: dict,
) -> list[dict]:
    current_at = str(iteration.get('finished_at', _now_utc()))
    lessons: list[dict] = []
    first_task = benchmark_result.get('task_results', [{}])[0] if benchmark_result.get('task_results') else {}
    intent_node = first_task.get('intent_node', {}) if isinstance(first_task.get('intent_node', {}), dict) else {}
    top_candidates = _safe_list(first_task.get('top_candidates'))

    if first_task:
        summary = (
            f"{benchmark_result.get('pack_name', 'benchmark')} task {first_task.get('task_id', 'task')}"
            f" observed {first_task.get('matched_expected_count', 0)}/{first_task.get('expected_count', 0)} matches"
        )
        lessons.append({
            'kind': 'retrieval',
            'summary': summary,
            'recommended_action': f"Prefer retrieval patterns that keep {', '.join(top_candidates[:2])}" if top_candidates else 'Refine candidate ranking signals',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
            'task_graph_path': str(first_task.get('task_graph_path', intent_node.get('task_graph_path', ''))),
            'intent_node': intent_node,
            'evidence': {
                'top_candidates': top_candidates,
                'matched_terms': _safe_list(first_task.get('matched_terms')),
                'score': _coerce_float(first_task.get('score'), 0.0),
            },
        })

    decision = str(iteration.get('decision', '')).lower()
    status = str(iteration.get('status', '')).lower()
    if decision == 'keep':
        lessons.append({
            'kind': 'policy',
            'summary': f"Iteration {_coerce_int(iteration.get('iteration'), 0)} kept score {iteration.get('score', 0)} under the current policy",
            'recommended_action': 'Reuse the same policy shape when the score gate is met',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
        })
    elif decision == 'discard':
        lessons.append({
            'kind': 'budget',
            'summary': f"Iteration {_coerce_int(iteration.get('iteration'), 0)} was discarded at score {iteration.get('score', 0)}",
            'recommended_action': 'Tighten budget controls or improve candidate recall before retrying',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
            'evidence': {
                'score_gate': iteration.get('score_gate'),
                'best_score': iteration.get('best_score'),
                'status': status,
            },
        })
    elif decision == 'crash':
        lessons.append({
            'kind': 'safety',
            'summary': f"Iteration {_coerce_int(iteration.get('iteration'), 0)} crashed and should rollback mutation zones",
            'recommended_action': 'Confirm allowlisted mutation zones and strict gate outputs before the next run',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
        })

    lockfile_signature = trust_summary.get('lockfile_signature', {}) if isinstance(trust_summary.get('lockfile_signature'), dict) else {}
    revocations = trust_summary.get('revocations', {}) if isinstance(trust_summary.get('revocations'), dict) else {}
    if lockfile_signature and not bool(lockfile_signature.get('valid', True)):
        lessons.append({
            'kind': 'trust',
            'summary': str(lockfile_signature.get('message', 'Lockfile signature is invalid')),
            'recommended_action': 'Refresh the lockfile or fix the signing key before trusting this run',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
            'evidence': {'state': lockfile_signature.get('state', 'invalid')},
        })
    elif revocations.get('revoked_trusted_key_ids'):
        lessons.append({
            'kind': 'trust',
            'summary': f"Revoked trusted keys present: {', '.join(_safe_list(revocations.get('revoked_trusted_key_ids')))}",
            'recommended_action': 'Exclude revoked keys from future trust decisions',
            'session_id': session_id,
            'iteration': _coerce_int(iteration.get('iteration'), 0),
            'scenario_id': session_manifest.get('scenario', {}).get('scenario_id', ''),
        })

    deduped: list[dict] = []
    seen: set[str] = set()
    for lesson in lessons:
        lesson = dict(lesson)
        dedupe_key = _lesson_dedupe_key(lesson)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lesson['dedupe_key'] = dedupe_key
        lesson['created_at'] = current_at
        lesson['decay'] = {
            'half_life_days': LESSON_DECAY_HALF_LIFE_DAYS,
            'score': LESSON_DECAY_WEIGHT,
            'updated_at': current_at,
        }
        deduped.append(lesson)
    return deduped


def _load_lesson_store(cwd: Path) -> dict:
    path = cwd / AUTONOMY_LESSONS_PATH
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return {'kind': 'autonomy-learning-store', 'schema_version': SESSION_SCHEMA_VERSION, 'updated_at': '', 'lessons': []}
    payload.setdefault('kind', 'autonomy-learning-store')
    payload.setdefault('schema_version', SESSION_SCHEMA_VERSION)
    payload.setdefault('updated_at', '')
    payload.setdefault('lessons', [])
    if not isinstance(payload.get('lessons'), list):
        payload['lessons'] = []
    return payload


def _merge_lesson_store(cwd: Path, session_id: str, lessons: list[dict]) -> dict:
    if not lessons:
        store = _load_lesson_store(cwd)
        store['updated_at'] = _now_utc()
        _write_json(cwd / AUTONOMY_LESSONS_PATH, store)
        return store

    now = _now_utc()
    store = _load_lesson_store(cwd)
    lesson_map: dict[str, dict] = {
        str(entry.get('dedupe_key', '')): dict(entry)
        for entry in store.get('lessons', [])
        if isinstance(entry, dict) and str(entry.get('dedupe_key', '')).strip()
    }
    for lesson in lessons:
        key = str(lesson.get('dedupe_key', '')).strip() or _lesson_dedupe_key(lesson)
        existing = lesson_map.get(key)
        if existing is None:
            lesson = dict(lesson)
            lesson['dedupe_key'] = key
            lesson['first_seen_at'] = now
            lesson['last_seen_at'] = now
            lesson['session_ids'] = [session_id]
            lesson['occurrence_count'] = 1
            lesson['decay']['score'] = _lesson_decay_score(lesson['created_at'], now)
            lesson_map[key] = lesson
            continue

        session_ids = _safe_list(existing.get('session_ids'))
        if session_id not in session_ids:
            session_ids.append(session_id)
        first_seen_at = str(existing.get('first_seen_at', now))
        existing.update(lesson)
        existing['dedupe_key'] = key
        existing['first_seen_at'] = first_seen_at
        existing['last_seen_at'] = now
        existing['session_ids'] = session_ids
        existing['occurrence_count'] = _coerce_int(existing.get('occurrence_count'), 1) + 1
        existing_decay = existing.get('decay', {}) if isinstance(existing.get('decay'), dict) else {}
        existing['decay'] = {
            'half_life_days': _coerce_int(existing_decay.get('half_life_days'), LESSON_DECAY_HALF_LIFE_DAYS),
            'score': _lesson_decay_score(first_seen_at, now),
            'updated_at': now,
        }
        lesson_map[key] = existing

    store['updated_at'] = now
    store['lessons'] = sorted(lesson_map.values(), key=lambda item: (str(item.get('kind', '')), str(item.get('summary', ''))))
    _write_json(cwd / AUTONOMY_LESSONS_PATH, store)
    return store


def _write_retrieval_trace(paths: dict[str, Path], session_id: str, iteration: int, benchmark_result: dict, task_graph: dict, scenario: dict) -> Path:
    trace_dir = paths['retrieval_traces_dir']
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f'iteration-{int(iteration):04d}.json'
    trace = {
        'kind': 'autonomy-retrieval-trace',
        'schema_version': SESSION_SCHEMA_VERSION,
        'session_id': session_id,
        'iteration': iteration,
        'scenario': scenario,
        'task_graph_root_path': task_graph.get('root_path', ''),
        'task_graph_paths': task_graph.get('path_index', {}),
        'tasks': [],
    }
    for task in benchmark_result.get('task_results', []):
        if not isinstance(task, dict):
            continue
        trace['tasks'].append({
            'task_id': task.get('task_id', ''),
            'task_graph_path': task.get('task_graph_path', ''),
            'intent_node': task.get('intent_node', {}),
            'expected_skills': _safe_list(task.get('expected_skills')),
            'matched_terms': _safe_list(task.get('matched_terms')),
            'top_candidates': _safe_list(task.get('top_candidates')),
            'score': task.get('score', 0.0),
            'matched_expected_count': task.get('matched_expected_count', 0),
            'expected_count': task.get('expected_count', 0),
            'candidate_count': task.get('candidate_count', 0),
            'candidate_reasons': task.get('candidate_reasons', []),
        })
    _write_json(trace_path, trace)
    return trace_path


def _capture_mutation_snapshot(cwd: Path, session_id: str, iteration: int, mutation_zones: list[Path]) -> dict:
    snapshot_root = AUTONOMY_SNAPSHOTS_ROOT / session_id / f'iteration-{int(iteration):04d}'
    zone_root = snapshot_root / 'zones'
    entries: list[dict] = []
    for zone in mutation_zones:
        entry = {
            'source_path': zone.as_posix(),
            'zone_name': _safe_zone_name(zone, cwd),
            'exists_before': zone.exists(),
            'kind': 'missing',
            'backup_path': '',
        }
        if not zone.exists():
            entries.append(entry)
            continue
        backup_path = zone_root / entry['zone_name']
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if zone.is_dir():
            shutil.copytree(zone, backup_path)
            entry['kind'] = 'directory'
        else:
            shutil.copy2(zone, backup_path)
            entry['kind'] = 'file'
        entry['backup_path'] = backup_path.as_posix()
        entries.append(entry)
    manifest = {
        'kind': 'autonomy-mutation-snapshot',
        'schema_version': SESSION_SCHEMA_VERSION,
        'session_id': session_id,
        'iteration': iteration,
        'created_at': _now_utc(),
        'zones': entries,
    }
    _write_json(snapshot_root / 'snapshot.json', manifest)
    return manifest


def _restore_mutation_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        return {'restored': 0, 'skipped': True, 'errors': []}
    restored = 0
    errors: list[str] = []
    for zone in reversed([entry for entry in snapshot.get('zones', []) if isinstance(entry, dict)]):
        source_path = zone.get('source_path')
        backup_path = zone.get('backup_path')
        if not isinstance(source_path, str) or not source_path.strip():
            continue
        target = Path(source_path)
        backup = Path(backup_path) if isinstance(backup_path, str) and backup_path.strip() else None
        try:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if backup is not None and backup.exists():
                if zone.get('kind') == 'directory':
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(backup, target)
                elif zone.get('kind') == 'file':
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                restored += 1
        except Exception as exc:
            errors.append(f'{target.as_posix()}: {exc}')
    return {'restored': restored, 'errors': errors, 'skipped': False}

def _candidate_signature(candidate: Any) -> set[str]:
    metadata = getattr(candidate, 'metadata', {}) or {}
    fields: list[Any] = [
        getattr(candidate, 'name', ''), getattr(candidate, 'install_ref', ''), getattr(candidate, 'source', ''),
        getattr(candidate, 'category', ''), ' '.join(getattr(candidate, 'tags', []) or []), metadata.get('name'),
        metadata.get('skill'), metadata.get('slug'), metadata.get('id'), metadata.get('title'),
        metadata.get('install_ref'), metadata.get('install_url'),
    ]
    tokens: set[str] = set()
    for field in fields:
        tokens.update(_tokenize(field))
    return tokens


def _expected_signature(skill_name: str) -> set[str]:
    return set(_tokenize(skill_name))


def _skill_similarity(expected: set[str], candidate: set[str]) -> float:
    if not expected or not candidate:
        return 0.0
    overlap = len(expected & candidate)
    if overlap == 0:
        return 0.0
    coverage = overlap / len(expected)
    precision = overlap / len(candidate)
    jaccard = overlap / len(expected | candidate)
    return round(max(jaccard, (coverage + precision) / 2), 4)


def _infer_task_profile(base_profile: dict, task: dict) -> dict:
    goal = ' '.join([str(task.get('title', '')), str(task.get('goal', '')), ' '.join(_safe_list(task.get('expected_skills')))]).lower()
    profile = copy.deepcopy(base_profile)
    inferred_app_type = profile.get('app_type', 'application')
    if any(token in goal for token in ['library', 'package', 'publish', 'release']):
        inferred_app_type = 'library'
    elif any(token in goal for token in ['cli', 'command line', 'terminal']):
        inferred_app_type = 'cli-tool'
    elif 'fullstack' in goal or ('frontend' in goal and 'backend' in goal):
        inferred_app_type = 'fullstack-app'
    elif any(token in goal for token in ['frontend', 'ui', 'browser']):
        inferred_app_type = 'web-app'
    elif any(token in goal for token in ['api', 'backend', 'service']):
        inferred_app_type = 'api-service'

    priorities = list(profile.get('priorities', []))
    if inferred_app_type == 'library':
        priorities.extend(['packaging', 'testing', 'publish', 'verification'])
    elif inferred_app_type == 'cli-tool':
        priorities.extend(['debugging', 'testing', 'verification'])
    elif inferred_app_type == 'fullstack-app':
        priorities.extend(['frontend', 'backend', 'integration', 'testing'])
    elif inferred_app_type == 'web-app':
        priorities.extend(['frontend', 'ui', 'testing'])
    elif inferred_app_type == 'api-service':
        priorities.extend(['backend', 'api', 'testing', 'verification'])
    elif any(token in goal for token in ['agent', 'workflow', 'autonomous']):
        priorities.extend(['automation', 'workflow', 'context-engineering', 'verification'])
    elif any(token in goal for token in ['debug', 'bug', 'fix']):
        priorities.extend(['debugging', 'verification', 'testing'])
    elif any(token in goal for token in ['test', 'verify', 'validation']):
        priorities.extend(['testing', 'verification'])

    languages = list(profile.get('languages', []))
    if 'python' not in {item.lower() for item in languages} and 'python' in goal:
        languages.append('python')
    if not languages:
        languages = ['python'] if 'python' in goal else ['unknown']

    frameworks = list(profile.get('frameworks', []))
    if 'pytest' in goal and 'pytest' not in {item.lower() for item in frameworks}:
        frameworks.append('pytest')

    target_tools = list(profile.get('target_tools', [])) or ['codex', 'claude']
    profile.update({
        'idea': str(task.get('goal', profile.get('idea', 'Recommendation benchmark'))),
        'app_type': inferred_app_type,
        'languages': list(dict.fromkeys(languages)),
        'frameworks': list(dict.fromkeys(frameworks)),
        'priorities': list(dict.fromkeys([item for item in priorities if item])),
        'target_tools': list(dict.fromkeys(target_tools)),
    })
    return profile


def _task_score(task: dict, recommendations: list[tuple[Any, dict]]) -> dict:
    expected = [item for item in _safe_list(task.get('expected_skills')) if item]
    expected_signatures = [(skill, _expected_signature(skill)) for skill in expected]
    candidate_signatures = []
    for position, (candidate, explanation) in enumerate(recommendations, start=1):
        candidate_signatures.append({
            'position': position,
            'name': getattr(candidate, 'name', ''),
            'signature': _candidate_signature(candidate),
            'reasons': list(explanation.get('reasons', [])) if isinstance(explanation, dict) else [],
        })

    matches: list[dict] = []
    best_similarities: list[float] = []
    matched_expected_count = 0
    for expected_name, expected_signature in expected_signatures:
        best = {'similarity': 0.0, 'candidate': '', 'position': 0}
        for candidate in candidate_signatures:
            similarity = _skill_similarity(expected_signature, candidate['signature'])
            if similarity > best['similarity']:
                best = {'similarity': similarity, 'candidate': candidate['name'], 'position': candidate['position']}
        best_similarities.append(best['similarity'])
        if best['similarity'] >= MATCH_THRESHOLD:
            matched_expected_count += 1
        matches.append({'expected': expected_name, **best})

    expected_count = len(expected_signatures)
    predicted_count = max(1, len(candidate_signatures))
    recall = matched_expected_count / expected_count if expected_count else 0.0
    precision = matched_expected_count / predicted_count if predicted_count else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    mean_similarity = sum(best_similarities) / expected_count if expected_count else 0.0
    score = round((0.65 * f1 + 0.35 * mean_similarity) * 100, 2)
    return {
        'score': score,
        'expected_count': expected_count,
        'matched_expected_count': matched_expected_count,
        'recall': round(recall, 4),
        'precision': round(precision, 4),
        'f1': round(f1, 4),
        'mean_similarity': round(mean_similarity, 4),
        'matches': matches,
        'top_candidates': [candidate['name'] for candidate in candidate_signatures[:5]],
        'candidate_reasons': [
            {
                'position': candidate['position'],
                'name': candidate['name'],
                'reasons': candidate['reasons'],
            }
            for candidate in candidate_signatures[:5]
        ],
    }


def _evaluate_recommendation_pack(
    cwd: Path,
    base_profile: dict,
    benchmark_pack: dict,
    recommendation_limit: int,
    *,
    task_graph: dict | None = None,
    intent: dict | None = None,
) -> dict:
    tasks = benchmark_pack.get('tasks', [])
    if not tasks:
        return {'pack_name': benchmark_pack.get('name', 'recommendation_tasks'), 'pack_path': benchmark_pack.get('pack_path', ''), 'task_count': 0, 'score': 0.0, 'matched_expected_count': 0, 'expected_count': 0, 'task_results': []}

    task_results: list[dict] = []
    total_score = 0.0
    total_expected = 0
    total_matched = 0
    path_index = task_graph.get('path_index', {}) if isinstance(task_graph, dict) else {}
    for task in tasks:
        scenario_profile = _infer_task_profile(base_profile, task)
        recommendations = explain_recommendations_for_profile(scenario_profile, cwd, limit=recommendation_limit)
        task_result = _task_score(task, recommendations)
        task_id = str(task.get('id', ''))
        task_result.update({
            'task_id': task_id,
            'title': str(task.get('title', '')),
            'goal': str(task.get('goal', '')),
            'expected_skills': _safe_list(task.get('expected_skills')),
            'candidate_count': len(recommendations),
            'task_graph_path': str(path_index.get(task_id, '')),
            'intent_node': dict(intent or {}),
        })
        task_results.append(task_result)
        total_score += task_result['score']
        total_expected += task_result['expected_count']
        total_matched += task_result['matched_expected_count']

    return {
        'pack_name': benchmark_pack.get('name', 'recommendation_tasks'),
        'pack_path': benchmark_pack.get('pack_path', ''),
        'task_count': len(task_results),
        'score': round(total_score / len(task_results), 2),
        'matched_expected_count': total_matched,
        'expected_count': total_expected,
        'task_results': task_results,
    }


def _normalize_command(command: Sequence[str] | str | None) -> list[str]:
    if command is None:
        return list(DEFAULT_TEST_COMMAND)
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command if str(part).strip()]


def _run_strict_gate(command: Sequence[str] | str | None, cwd: Path) -> dict:
    args = _normalize_command(command)
    start = time.monotonic()
    try:
        completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)
        output_lines = (completed.stdout or '').splitlines() + (completed.stderr or '').splitlines()
        return {
            'command': args, 'returncode': completed.returncode, 'elapsed_seconds': round(time.monotonic() - start, 4),
            'passed': completed.returncode == 0, 'stdout': completed.stdout, 'stderr': completed.stderr,
            'output_excerpt': '\n'.join(output_lines[-40:]),
        }
    except FileNotFoundError as exc:
        return {'command': args, 'returncode': 127, 'elapsed_seconds': round(time.monotonic() - start, 4), 'passed': False, 'stdout': '', 'stderr': str(exc), 'output_excerpt': str(exc), 'error': 'command_not_found'}


def _session_paths(cwd: Path, session_id: str) -> dict[str, Path]:
    runs_dir = cwd / AUTONOMY_RUNS_DIR
    session_dir = runs_dir / session_id
    return {
        'root': cwd / AUTONOMY_ROOT,
        'runs': runs_dir,
        'session_dir': session_dir,
        'session_file': runs_dir / f'{session_id}.json',
        'iterations_dir': session_dir / 'iterations',
        'retrieval_traces_dir': session_dir / 'retrieval_traces',
        'pointer': cwd / AUTONOMY_LATEST_POINTER,
        'results': cwd / AUTONOMY_RESULTS_TSV,
    }

def _write_results_row(results_path: Path, row: dict) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ['timestamp', 'row_type', 'session_id', 'iteration', 'decision', 'status', 'score', 'score_gate', 'best_score', 'non_improving_streak', 'strict_gate_passed', 'strict_gate_returncode', 'benchmark_pack', 'benchmark_tasks', 'benchmark_score', 'benchmark_matched_expected', 'benchmark_expected', 'elapsed_seconds', 'stop_reason', 'details']
    write_header = not results_path.exists()
    with results_path.open('a', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        if write_header:
            writer.writeheader()
        writer.writerow({key: _jsonable(row.get(key, '')) for key in fieldnames})


def _write_pointer(pointer_path: Path, session: dict) -> None:
    payload = {'kind': 'latest-pointer', 'schema_version': SESSION_SCHEMA_VERSION, 'session_id': session.get('session_id', ''), 'session_path': session.get('session_path', ''), 'status': session.get('status', ''), 'updated_at': session.get('updated_at', _now_utc()), 'summary': summarize_session(session), '_base_dir': pointer_path.parent.as_posix()}
    _write_json(pointer_path, payload)


def _persist_session(paths: dict[str, Path], session: dict) -> None:
    session['session_path'] = paths['session_file'].relative_to(paths['root']).as_posix()
    session['updated_at'] = _now_utc()
    _write_json(paths['session_file'], session)
    _write_json(paths['session_dir'] / 'session.json', session)
    _write_json(paths['session_dir'] / 'state.json', session)
    _write_pointer(paths['pointer'], session)


def _append_iteration_state(paths: dict[str, Path], iteration: dict) -> None:
    _write_json(paths['iterations_dir'] / f"iteration-{int(iteration['iteration']):04d}.json", iteration)


def _stop_reason_from_iteration_limit(iteration: int, max_iterations: int, elapsed_hours: float, max_hours: float) -> str | None:
    if max_hours >= 0 and elapsed_hours >= max_hours:
        return 'max_hours'
    if iteration >= max_iterations:
        return 'max_iterations'
    return None


def summarize_session(session: dict | str | Path | None) -> dict:
    payload = _load_session_payload(session)
    if not isinstance(payload, dict):
        return {'session_id': '', 'domain': '', 'status': 'missing', 'iterations': 0, 'kept': 0, 'discarded': 0, 'crashed': 0, 'best_score': 0.0, 'final_score': 0.0, 'score_gate': None, 'stop_reason': '', 'preflight_clean': False, 'duration_seconds': 0.0, 'benchmark_pack': '', 'task_count': 0, 'matched_expected_count': 0, 'expected_count': 0, 'score': 0.0}

    iterations = sorted([item for item in payload.get('iterations', []) if isinstance(item, dict)], key=lambda item: _coerce_int(item.get('iteration'), 0))
    last_iteration = iterations[-1] if iterations else {}
    counts = {'keep': 0, 'discard': 0, 'crash': 0}
    for iteration in iterations:
        decision = str(iteration.get('decision', '')).lower()
        if decision in counts:
            counts[decision] += 1

    benchmark = payload.get('benchmark', {}) if isinstance(payload.get('benchmark', {}), dict) else {}
    summary = payload.get('summary', {}) if isinstance(payload.get('summary', {}), dict) else {}
    preflight = payload.get('preflight', {}) if isinstance(payload.get('preflight', {}), dict) else {}
    started_at = str(payload.get('started_at', ''))
    finished_at = str(payload.get('finished_at', ''))
    duration_seconds = _coerce_float(payload.get('duration_seconds'), 0.0)
    if duration_seconds <= 0 and started_at and finished_at:
        try:
            start_dt = dt.datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            end_dt = dt.datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
            duration_seconds = max(0.0, (end_dt - start_dt).total_seconds())
        except Exception:
            duration_seconds = 0.0

    final_score = _coerce_float(last_iteration.get('score'), _coerce_float(summary.get('score'), 0.0))
    best_score = _coerce_float(payload.get('best_score'), final_score)
    if payload.get('best_score') is None and iterations:
        best_score = max(_coerce_float(item.get('score'), 0.0) for item in iterations)

    return {
        'session_id': str(payload.get('session_id', '')),
        'domain': str(payload.get('domain', '')),
        'status': str(payload.get('status', 'unknown')),
        'iterations': len(iterations),
        'kept': counts['keep'],
        'discarded': counts['discard'],
        'crashed': counts['crash'],
        'best_score': round(best_score, 2),
        'final_score': round(final_score, 2),
        'score_gate': payload.get('score_gate'),
        'stop_reason': str(payload.get('stop_reason', '')),
        'preflight_clean': _coerce_bool(preflight.get('clean'), False),
        'duration_seconds': round(duration_seconds, 4),
        'benchmark_pack': str(benchmark.get('name', '')),
        'task_count': _coerce_int(benchmark.get('task_count'), len(benchmark.get('tasks', [])) if isinstance(benchmark.get('tasks'), list) else 0),
        'matched_expected_count': _coerce_int(summary.get('matched_expected_count'), 0),
        'expected_count': _coerce_int(summary.get('expected_count'), 0),
        'score': _coerce_float(summary.get('score'), final_score),
        'decision_counts': counts,
        'last_decision': str(last_iteration.get('decision', '')),
        'run_manifest': payload.get('run_manifest', {}),
        'trust_summary': payload.get('trust_summary', {}),
    }


def load_latest_session(cwd: Path | str | None = None) -> dict | None:
    root = _resolve_cwd(cwd)
    pointer = _load_json(root / AUTONOMY_LATEST_POINTER)
    if isinstance(pointer, dict):
        payload = _load_session_payload(pointer)
        if isinstance(payload, dict):
            return payload

    runs_dir = root / AUTONOMY_RUNS_DIR
    if not runs_dir.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for path in runs_dir.glob('*.json'):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        timestamp = _coerce_float(payload.get('updated_at_epoch'), 0.0)
        if timestamp <= 0:
            timestamp = path.stat().st_mtime
        candidates.append((timestamp, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].name))
    latest = _load_json(candidates[-1][1])
    return latest if isinstance(latest, dict) else None

def run_autonomy_session(
    *,
    cwd: Path | str | None = None,
    domain: str = 'recommend',
    benchmark_pack: str | Path | dict | None = None,
    max_iterations: int = 3,
    max_hours: float = 1.0,
    max_non_improving: int = 2,
    score_gate: float | None = 60.0,
    recommendation_limit: int = 5,
    strict_test_command: Sequence[str] | str | None = None,
    strict_gate: bool = True,
    mutation_zones: Sequence[str | Path] | str | Path | None = None,
    rollback_on_discard: bool = True,
    rollback_on_crash: bool = True,
    max_depth: int | None = None,
    replay_latest: bool = False,
    task_executor: Callable[[dict, dict[str, Any]], dict[str, Any]] | None = None,
    now_fn: Callable[[], dt.datetime] | None = None,
) -> dict:
    root = _resolve_cwd(cwd)
    if domain.lower() not in SUPPORTED_DOMAINS:
        raise ValueError(f'unsupported autonomy domain: {domain}')

    max_iterations = max(0, _coerce_int(max_iterations, 0))
    max_non_improving = max(0, _coerce_int(max_non_improving, 0))
    max_hours = max(0.0, _coerce_float(max_hours, 0.0))
    recommendation_limit = max(1, _coerce_int(recommendation_limit, 5))
    score_gate_value = None if score_gate is None else _coerce_float(score_gate, 0.0)
    clock = now_fn or (lambda: dt.datetime.now(dt.timezone.utc).replace(microsecond=0))
    session_id = clock().strftime('%Y%m%dT%H%M%SZ') + f'-{uuid.uuid4().hex[:8]}'
    paths = _session_paths(root, session_id)
    paths['session_dir'].mkdir(parents=True, exist_ok=True)
    paths['iterations_dir'].mkdir(parents=True, exist_ok=True)
    paths['retrieval_traces_dir'].mkdir(parents=True, exist_ok=True)
    paths['runs'].mkdir(parents=True, exist_ok=True)
    paths['root'].mkdir(parents=True, exist_ok=True)

    normalized_mutation_zones, skipped_mutation_zones = _normalize_mutation_zones(root, mutation_zones)
    if not normalized_mutation_zones:
        default_candidates = [root / 'src', root / '.agent' / 'skills']
        normalized_mutation_zones, default_skipped = _normalize_mutation_zones(root, [path for path in default_candidates if path.exists()])
        skipped_mutation_zones.extend(default_skipped)

    profile = _load_profile(root)
    benchmark = _load_benchmark_pack(root, benchmark_pack)
    benchmark_manifest = _benchmark_summary(benchmark)
    context_manifest = _context_index_summary(root)
    replay_session = load_latest_session(root) if replay_latest else None
    task_graph = _build_task_graph(session_id, benchmark)
    intent = {
        'kind': 'typed-intent',
        'intent_id': f'intent-{session_id}',
        'intent_type': 'recommendation-optimization',
        'goal': f"Improve recommendation quality on benchmark '{benchmark_manifest.get('name', 'benchmark')}'",
        'constraints': [
            'mutation-safe',
            'bounded-runtime',
            'reproducible-manifest',
            'strict-keep-discard-gate',
        ],
        'task_graph_root_path': task_graph.get('root_path', ''),
    }
    runtime_policy = _build_runtime_policy(
        domain=domain,
        max_iterations=max_iterations,
        max_hours=max_hours,
        max_non_improving=max_non_improving,
        score_gate=score_gate_value,
        recommendation_limit=recommendation_limit,
        strict_test_command=_normalize_command(strict_test_command),
        strict_gate=bool(strict_gate),
        mutation_zones=normalized_mutation_zones,
        skipped_mutation_zones=skipped_mutation_zones,
        max_depth=max_depth,
    )
    evaluation_surface = _build_evaluation_surface(session_id, benchmark, replay_session=replay_session)
    trust_summary = _build_trust_summary(root, profile)
    run_manifest = {
        'schema_version': SESSION_SCHEMA_VERSION,
        'session_id': session_id,
        'domain': domain,
        'benchmark': benchmark_manifest,
        'context_index': context_manifest,
        'evaluation_surface': evaluation_surface,
        'runtime_policy_hash': runtime_policy.get('hash', ''),
        'trust_signature_state': trust_summary.get('lockfile_signature_state', ''),
        'generated_at': _now_utc(),
    }
    run_manifest['manifest_hash'] = _stable_json_hash(run_manifest)
    preflight = _git_preflight(root)
    started_at = _now_utc()
    session = {
        'kind': 'autonomy-session', 'schema_version': SESSION_SCHEMA_VERSION, 'session_id': session_id,
        'domain': domain, 'cwd': root.as_posix(), 'started_at': started_at, 'updated_at': started_at,
        'finished_at': '', 'status': 'running', 'stop_reason': '', 'final_decision': '',
        'score_gate': score_gate_value, 'max_iterations': max_iterations, 'max_hours': max_hours,
        'max_non_improving': max_non_improving, 'recommendation_limit': recommendation_limit,
        'strict_test_command': _normalize_command(strict_test_command), 'strict_gate': bool(strict_gate),
        'profile': profile, 'benchmark': benchmark,
        'intent': intent, 'task_graph': task_graph,
        'runtime_policy': runtime_policy,
        'evaluation_surface': evaluation_surface,
        'run_manifest': run_manifest,
        'mutation_safety': {
            'zones': [path.as_posix() for path in normalized_mutation_zones],
            'skipped_zones': skipped_mutation_zones,
            'rollback_on_discard': bool(rollback_on_discard),
            'rollback_on_crash': bool(rollback_on_crash),
            'snapshots_enabled': bool(normalized_mutation_zones),
            'last_snapshot': {},
            'last_rollback': {},
        },
        'trust_summary': trust_summary,
        'lessons': [],
        'preflight': preflight, 'iterations': [], 'best_score': None, 'best_iteration': None,
        'last_score': None, 'last_strict_gate': {}, 'summary': {}, 'duration_seconds': 0.0,
    }

    if not preflight.get('clean'):
        session['status'] = 'blocked'
        session['stop_reason'] = str(preflight.get('reason', 'preflight_dirty_git'))
        session['final_decision'] = 'crash'
        session['finished_at'] = _now_utc()
        session['summary'] = summarize_session(session)
        _persist_session(paths, session)
        _write_results_row(paths['results'], {
            'timestamp': session['finished_at'], 'row_type': 'preflight', 'session_id': session_id, 'iteration': 0,
            'decision': 'crash', 'status': session['status'], 'score': 0.0, 'score_gate': score_gate_value if score_gate_value is not None else '',
            'best_score': '', 'non_improving_streak': 0, 'strict_gate_passed': False, 'strict_gate_returncode': '',
            'benchmark_pack': benchmark.get('name', ''), 'benchmark_tasks': _coerce_int(benchmark.get('task_count'), len(benchmark.get('tasks', []))),
            'benchmark_score': 0.0, 'benchmark_matched_expected': 0, 'benchmark_expected': 0, 'elapsed_seconds': 0.0,
            'stop_reason': session['stop_reason'], 'details': f"preflight blocked: {preflight.get('reason', 'dirty git')}",
        })
        return session

    started_monotonic = time.monotonic()
    best_score = float('-inf')
    non_improving_streak = 0
    stop_reason = ''
    executor = task_executor

    for iteration in range(1, max_iterations + 1):
        if iteration > 1 and max_hours >= 0 and (time.monotonic() - started_monotonic) / 3600.0 >= max_hours:
            stop_reason = 'max_hours'
            break

        iteration_started_at = _now_utc()
        mutation_snapshot = _capture_mutation_snapshot(root, session_id, iteration, normalized_mutation_zones) if normalized_mutation_zones else {
            'kind': 'autonomy-mutation-snapshot',
            'schema_version': SESSION_SCHEMA_VERSION,
            'session_id': session_id,
            'iteration': iteration,
            'created_at': _now_utc(),
            'zones': [],
            'skipped': True,
        }
        strict_gate_result = _run_strict_gate(strict_test_command, root) if strict_gate else {
            'command': [],
            'returncode': 0,
            'elapsed_seconds': 0.0,
            'passed': True,
            'stdout': '',
            'stderr': '',
            'output_excerpt': 'strict gate disabled',
        }
        benchmark_result = _evaluate_recommendation_pack(
            root,
            profile,
            benchmark,
            recommendation_limit,
            task_graph=task_graph,
            intent=intent,
        )
        if executor is not None:
            try:
                task_result = executor(benchmark, {'cwd': root, 'profile': profile, 'benchmark': benchmark, 'iteration': iteration, 'session_id': session_id}) or {}
                if isinstance(task_result, dict):
                    benchmark_result = {
                        'pack_name': benchmark.get('name', benchmark_result['pack_name']),
                        'pack_path': benchmark_result.get('pack_path', ''),
                        'task_count': benchmark_result.get('task_count', 0),
                        'score': _coerce_float(task_result.get('score'), benchmark_result.get('score', 0.0)),
                        'matched_expected_count': _coerce_int(task_result.get('matched_expected_count'), benchmark_result.get('matched_expected_count', 0)),
                        'expected_count': _coerce_int(task_result.get('expected_count'), benchmark_result.get('expected_count', 0)),
                        'task_results': task_result.get('task_results', benchmark_result.get('task_results', [])),
                    }
            except Exception as exc:
                strict_gate_result = {'passed': False, 'returncode': 1, 'elapsed_seconds': 0.0, 'stdout': '', 'stderr': str(exc), 'output_excerpt': str(exc), 'error': 'task_executor_failed'}

        if not strict_gate_result.get('passed'):
            decision = 'crash'
            status = 'crashed'
            stop_reason = 'strict_gate_failed'
        else:
            current_score = _coerce_float(benchmark_result.get('score'), 0.0)
            passes_score_gate = score_gate_value is None or current_score >= score_gate_value
            improved = current_score > best_score
            if passes_score_gate and improved:
                decision = 'keep'
                status = 'kept'
                best_score = current_score
                non_improving_streak = 0
            else:
                decision = 'discard'
                status = 'discarded'
                non_improving_streak += 1
                if best_score == float('-inf'):
                    best_score = current_score

        current_score = _coerce_float(benchmark_result.get('score'), 0.0)
        finished_at = _now_utc()
        retrieval_trace_path = _write_retrieval_trace(
            paths,
            session_id,
            iteration,
            benchmark_result,
            task_graph,
            evaluation_surface.get('scenario', {}),
        )
        rollback_result = {'restored': 0, 'errors': [], 'skipped': True}
        if decision == 'discard' and rollback_on_discard:
            rollback_result = _restore_mutation_snapshot(mutation_snapshot)
        elif decision == 'crash' and rollback_on_crash:
            rollback_result = _restore_mutation_snapshot(mutation_snapshot)

        iteration_manifest = {
            'session_id': session_id,
            'iteration': iteration,
            'base_manifest_hash': run_manifest.get('manifest_hash', ''),
            'runtime_policy_hash': runtime_policy.get('hash', ''),
            'context_index_hash': context_manifest.get('hash', ''),
            'benchmark_hash': benchmark_manifest.get('hash', ''),
            'retrieval_trace': retrieval_trace_path.relative_to(root).as_posix(),
            'decision': decision,
            'status': status,
        }
        iteration_manifest['manifest_hash'] = _stable_json_hash(iteration_manifest)
        iteration_lessons = _extract_lessons_from_iteration(
            session_id=session_id,
            iteration={'iteration': iteration, 'decision': decision, 'status': status, 'score': current_score, 'score_gate': score_gate_value, 'best_score': best_score, 'finished_at': finished_at},
            benchmark_result=benchmark_result,
            trust_summary=trust_summary,
            session_manifest=evaluation_surface,
        )
        lesson_store = _merge_lesson_store(root, session_id, iteration_lessons)
        iteration_record = {
            'kind': 'autonomy-iteration', 'schema_version': SESSION_SCHEMA_VERSION, 'session_id': session_id,
            'iteration': iteration, 'started_at': iteration_started_at, 'finished_at': finished_at,
            'elapsed_seconds': round(time.monotonic() - started_monotonic, 4), 'decision': decision, 'status': status,
            'strict_gate': strict_gate_result, 'benchmark': benchmark_result, 'score': current_score, 'score_gate': score_gate_value,
            'best_score': None if best_score == float('-inf') else round(best_score, 2), 'non_improving_streak': non_improving_streak,
            'intent': intent,
            'task_graph': task_graph,
            'run_manifest': iteration_manifest,
            'retrieval_trace': retrieval_trace_path.relative_to(root).as_posix(),
            'lessons': iteration_lessons,
            'mutation_safety': {
                'snapshot': mutation_snapshot,
                'rollback_policy': {
                    'rollback_on_discard': bool(rollback_on_discard),
                    'rollback_on_crash': bool(rollback_on_crash),
                },
                'rollback_result': rollback_result,
            },
            'trust_summary': trust_summary,
        }
        session['iterations'].append(iteration_record)
        session['last_score'] = current_score
        session['last_strict_gate'] = strict_gate_result
        session['run_manifest'] = {
            **run_manifest,
            'iteration_count': len(session['iterations']),
            'best_score': None if best_score == float('-inf') else round(best_score, 2),
            'last_iteration_manifest_hash': iteration_manifest.get('manifest_hash', ''),
            'last_retrieval_trace': iteration_record.get('retrieval_trace', ''),
            'stop_reason': stop_reason,
            'status': session.get('status', 'running'),
        }
        session['run_manifest']['manifest_hash'] = _stable_json_hash(session['run_manifest'])
        session['lessons'] = lesson_store.get('lessons', [])[:20] if isinstance(lesson_store, dict) else []
        session['mutation_safety']['last_snapshot'] = mutation_snapshot
        session['mutation_safety']['last_rollback'] = rollback_result
        if decision == 'keep' or (session.get('best_score') is None and best_score != float('-inf')):
            session['best_score'] = round(best_score, 2)
            session['best_iteration'] = iteration

        _append_iteration_state(paths, iteration_record)
        first_task = benchmark_result.get('task_results', [{}])[0] if benchmark_result.get('task_results') else {}
        _write_results_row(paths['results'], {
            'timestamp': finished_at, 'row_type': 'iteration-summary', 'session_id': session_id, 'iteration': iteration,
            'decision': decision, 'status': status, 'score': current_score, 'score_gate': score_gate_value if score_gate_value is not None else '',
            'best_score': '' if best_score == float('-inf') else round(best_score, 2),
            'non_improving_streak': non_improving_streak, 'strict_gate_passed': bool(strict_gate_result.get('passed')),
            'strict_gate_returncode': strict_gate_result.get('returncode', ''), 'benchmark_pack': benchmark_result.get('pack_name', benchmark.get('name', '')),
            'benchmark_tasks': benchmark_result.get('task_count', 0), 'benchmark_score': benchmark_result.get('score', 0.0),
            'benchmark_matched_expected': benchmark_result.get('matched_expected_count', 0), 'benchmark_expected': benchmark_result.get('expected_count', 0),
            'elapsed_seconds': iteration_record['elapsed_seconds'], 'stop_reason': '',
            'details': '; '.join(filter(None, [
                f"strict_gate={strict_gate_result.get('returncode', '')}",
                f"matches={benchmark_result.get('matched_expected_count', 0)}/{benchmark_result.get('expected_count', 0)}",
                f"top={', '.join(_safe_list(first_task.get('top_candidates')))}",
                f"trace={iteration_record.get('retrieval_trace', '')}",
                f"rollback_restored={_coerce_int(rollback_result.get('restored'), 0)}",
            ])),
        })

        session['updated_at'] = finished_at
        session['summary'] = summarize_session(session)
        _persist_session(paths, session)

        if decision == 'crash':
            break
        if max_non_improving and non_improving_streak >= max_non_improving:
            stop_reason = 'max_non_improving'
            break
        stop_reason_candidate = _stop_reason_from_iteration_limit(iteration, max_iterations, (time.monotonic() - started_monotonic) / 3600.0, max_hours)
        if stop_reason_candidate:
            stop_reason = stop_reason_candidate
            break

    if not stop_reason:
        if len(session['iterations']) >= max_iterations:
            stop_reason = 'max_iterations'
        elif max_hours >= 0 and (time.monotonic() - started_monotonic) / 3600.0 >= max_hours:
            stop_reason = 'max_hours'
        elif max_non_improving and non_improving_streak >= max_non_improving:
            stop_reason = 'max_non_improving'
        elif session['iterations'] and session['iterations'][-1]['decision'] == 'crash':
            stop_reason = 'strict_gate_failed'
        else:
            stop_reason = 'completed'

    session['stop_reason'] = stop_reason
    session['status'] = 'crashed' if stop_reason == 'strict_gate_failed' else 'completed'
    session['final_decision'] = 'crash' if stop_reason == 'strict_gate_failed' else (session['iterations'][-1]['decision'] if session['iterations'] else '')
    session['finished_at'] = _now_utc()
    session['duration_seconds'] = round(time.monotonic() - started_monotonic, 4)
    session['run_manifest'] = {
        **session.get('run_manifest', run_manifest),
        'status': session['status'],
        'stop_reason': session['stop_reason'],
        'final_decision': session['final_decision'],
        'iteration_count': len(session['iterations']),
        'duration_seconds': session['duration_seconds'],
    }
    session['run_manifest']['manifest_hash'] = _stable_json_hash(session['run_manifest'])
    session['summary'] = summarize_session(session)
    _persist_session(paths, session)
    return session


run_autonomy = run_autonomy_session


def run(cwd: Path | str | None = None, **kwargs) -> dict:
    return run_autonomy_session(cwd=cwd, **kwargs)


def run_autonomy(cwd: Path | str | None = None, **kwargs) -> dict:
    return run_autonomy_session(cwd=cwd, **kwargs)


def run_autonomous(cwd: Path | str | None = None, **kwargs) -> dict:
    return run_autonomy_session(cwd=cwd, **kwargs)


load_autonomy_session = load_latest_session
status = load_latest_session
report = summarize_session


__all__ = ['run_autonomy_session', 'load_latest_session', 'summarize_session']



