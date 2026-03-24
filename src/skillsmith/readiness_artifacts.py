from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

REPORT_ARTIFACT_NAME = "report.json"
READINESS_PR_ARTIFACT_NAME = "readiness_pr.md"
SCORECARD_ARTIFACT_NAME = "scorecard.json"

ACTIVATION_PROXY_METRICS: dict[str, dict[str, Any]] = {
    "first_run_success_rate_pct": {
        "type": "number",
        "unit": "percent",
        "default": None,
        "description": "Percent of first repo readiness runs that reach a successful baseline.",
    },
    "time_to_first_readiness_minutes": {
        "type": "number",
        "unit": "minutes",
        "default": None,
        "description": "Median time from repo bootstrap to a shareable readiness report.",
    },
    "init_doctor_compose_report_completion_rate_pct": {
        "type": "number",
        "unit": "percent",
        "default": None,
        "description": "Percent of first sessions that complete init -> doctor -> compose -> report.",
    },
    "first_run_blocker_count": {
        "type": "integer",
        "unit": "count",
        "default": None,
        "description": "Average number of blockers surfaced during the first readiness run.",
    },
}

RETENTION_PROXY_METRICS: dict[str, dict[str, Any]] = {
    "day_7_return_rate_pct": {
        "type": "number",
        "unit": "percent",
        "default": None,
        "description": "Percent of users or teams returning within 7 days.",
    },
    "day_30_team_retention_pct": {
        "type": "number",
        "unit": "percent",
        "default": None,
        "description": "Percent of teams still actively using the workflow after 30 days.",
    },
    "repeat_readiness_report_rate_pct": {
        "type": "number",
        "unit": "percent",
        "default": None,
        "description": "Percent of repos that generate a second readiness report after the first run.",
    },
    "weekly_active_repo_count": {
        "type": "integer",
        "unit": "count",
        "default": None,
        "description": "Number of repositories producing a readiness report in the current week.",
    },
}


def _now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _json_text(payload: Any) -> str:
    return json.dumps(_json_safe(payload), indent=2, sort_keys=True)


def render_readiness_pr(report: dict[str, Any]) -> str:
    readiness = report.get("readiness_summary", {})
    blockers = readiness.get("blockers", []) if isinstance(readiness, dict) else []
    warnings = readiness.get("warnings", []) if isinstance(readiness, dict) else []
    blockers_text = ", ".join(str(item) for item in blockers if item not in (None, "")) or "none"
    warnings_text = ", ".join(str(item) for item in warnings if item not in (None, "")) or "none"
    lines = [
        "## Skillsmith Readiness",
        "",
        f"- Status: {str(readiness.get('status', '')).replace('_', ' ')}" if isinstance(readiness, dict) else "- Status: unknown",
        f"- Ready: {'yes' if isinstance(readiness, dict) and readiness.get('ready') else 'no'}",
        f"- Score: {readiness.get('score', 0)}/100" if isinstance(readiness, dict) else "- Score: 0/100",
        f"- Summary: {readiness.get('summary', '')}" if isinstance(readiness, dict) else "- Summary: unknown",
        f"- Profile source: {report.get('profile_source', 'unknown')}",
        f"- Starter pack: {report.get('starter_pack_label', 'unknown')}",
        f"- Blockers: {blockers_text}",
        f"- Warnings: {warnings_text}",
        "",
        "### Follow-up",
        "- Run `skillsmith doctor` for the full rendered-file and workflow-surface audit.",
        "- Run `skillsmith report --json` to capture the machine-readable readiness artifact.",
    ]
    return "\n".join(lines)


def build_readiness_scorecard(report: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    readiness = report.get("readiness_summary", {})
    if not isinstance(readiness, dict):
        readiness = {}
    metrics = {
        "activation": {name: spec["default"] for name, spec in ACTIVATION_PROXY_METRICS.items()},
        "retention": {name: spec["default"] for name, spec in RETENTION_PROXY_METRICS.items()},
    }
    return {
        "generated_at": generated_at or _now_utc(),
        "schema_version": 1,
        "readiness": {
            "ready": bool(readiness.get("ready", False)),
            "status": str(readiness.get("status", "unknown")),
            "score": readiness.get("score"),
            "summary": readiness.get("summary"),
            "blockers": list(readiness.get("blockers", [])) if isinstance(readiness.get("blockers", []), list) else [],
            "warnings": list(readiness.get("warnings", [])) if isinstance(readiness.get("warnings", []), list) else [],
        },
        "artifact_set": {
            "report_json": REPORT_ARTIFACT_NAME,
            "readiness_pr_md": READINESS_PR_ARTIFACT_NAME,
            "scorecard_json": SCORECARD_ARTIFACT_NAME,
        },
        "metrics": metrics,
        "metric_schema": {
            "activation": ACTIVATION_PROXY_METRICS,
            "retention": RETENTION_PROXY_METRICS,
        },
    }


def write_readiness_artifacts(artifact_dir: Path, report: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Path]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        REPORT_ARTIFACT_NAME: artifact_dir / REPORT_ARTIFACT_NAME,
        READINESS_PR_ARTIFACT_NAME: artifact_dir / READINESS_PR_ARTIFACT_NAME,
        SCORECARD_ARTIFACT_NAME: artifact_dir / SCORECARD_ARTIFACT_NAME,
    }
    outputs[REPORT_ARTIFACT_NAME].write_text(_json_text(report) + "\n", encoding="utf-8")
    outputs[READINESS_PR_ARTIFACT_NAME].write_text(render_readiness_pr(report) + "\n", encoding="utf-8")
    outputs[SCORECARD_ARTIFACT_NAME].write_text(
        _json_text(build_readiness_scorecard(report, generated_at=generated_at)) + "\n",
        encoding="utf-8",
    )
    return outputs
