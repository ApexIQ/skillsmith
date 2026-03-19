from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from . import TEMPLATE_DIR, sanitize_json
from .init import _infer_project_profile
from .providers import explain_recommendations_for_profile, get_profile
from .rendering import load_project_profile

AUTONOMY_ROOT = Path('.agent') / 'autonomy'
AUTONOMY_RUNS_DIR = AUTONOMY_ROOT / 'runs'
AUTONOMY_BENCHMARKS_DIR = AUTONOMY_ROOT / 'benchmarks'
AUTONOMY_RESULTS_TSV = AUTONOMY_ROOT / 'results.tsv'
AUTONOMY_LATEST_POINTER = AUTONOMY_ROOT / 'latest.json'
TEMPLATE_AUTONOMY_DIR = TEMPLATE_DIR / '.agent' / 'autonomy'
DEFAULT_BENCHMARK_PACK = 'recommendation_tasks.json'
DEFAULT_TEST_COMMAND = ('uv', 'run', 'python', '-m', 'unittest', 'discover', 'tests', '-v')
SUPPORTED_DOMAINS = {'recommend', 'recommendation'}
SESSION_SCHEMA_VERSION = 1
MATCH_THRESHOLD = 0.5
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
    }


def _evaluate_recommendation_pack(cwd: Path, base_profile: dict, benchmark_pack: dict, recommendation_limit: int) -> dict:
    tasks = benchmark_pack.get('tasks', [])
    if not tasks:
        return {'pack_name': benchmark_pack.get('name', 'recommendation_tasks'), 'pack_path': benchmark_pack.get('pack_path', ''), 'task_count': 0, 'score': 0.0, 'matched_expected_count': 0, 'expected_count': 0, 'task_results': []}

    task_results: list[dict] = []
    total_score = 0.0
    total_expected = 0
    total_matched = 0
    for task in tasks:
        scenario_profile = _infer_task_profile(base_profile, task)
        recommendations = explain_recommendations_for_profile(scenario_profile, cwd, limit=recommendation_limit)
        task_result = _task_score(task, recommendations)
        task_result.update({
            'task_id': str(task.get('id', '')),
            'title': str(task.get('title', '')),
            'goal': str(task.get('goal', '')),
            'expected_skills': _safe_list(task.get('expected_skills')),
            'candidate_count': len(recommendations),
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
    return {'root': cwd / AUTONOMY_ROOT, 'runs': runs_dir, 'session_dir': session_dir, 'session_file': runs_dir / f'{session_id}.json', 'iterations_dir': session_dir / 'iterations', 'pointer': cwd / AUTONOMY_LATEST_POINTER, 'results': cwd / AUTONOMY_RESULTS_TSV}

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
    paths['runs'].mkdir(parents=True, exist_ok=True)
    paths['root'].mkdir(parents=True, exist_ok=True)

    profile = _load_profile(root)
    benchmark = _load_benchmark_pack(root, benchmark_pack)
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
        strict_gate_result = _run_strict_gate(strict_test_command, root) if strict_gate else {
            'command': [],
            'returncode': 0,
            'elapsed_seconds': 0.0,
            'passed': True,
            'stdout': '',
            'stderr': '',
            'output_excerpt': 'strict gate disabled',
        }
        benchmark_result = _evaluate_recommendation_pack(root, profile, benchmark, recommendation_limit)
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
        iteration_record = {
            'kind': 'autonomy-iteration', 'schema_version': SESSION_SCHEMA_VERSION, 'session_id': session_id,
            'iteration': iteration, 'started_at': iteration_started_at, 'finished_at': finished_at,
            'elapsed_seconds': round(time.monotonic() - started_monotonic, 4), 'decision': decision, 'status': status,
            'strict_gate': strict_gate_result, 'benchmark': benchmark_result, 'score': current_score, 'score_gate': score_gate_value,
            'best_score': None if best_score == float('-inf') else round(best_score, 2), 'non_improving_streak': non_improving_streak,
        }
        session['iterations'].append(iteration_record)
        session['last_score'] = current_score
        session['last_strict_gate'] = strict_gate_result
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
            'details': '; '.join(filter(None, [f"strict_gate={strict_gate_result.get('returncode', '')}", f"matches={benchmark_result.get('matched_expected_count', 0)}/{benchmark_result.get('expected_count', 0)}", f"top={', '.join(_safe_list(first_task.get('top_candidates')))}"])),
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



