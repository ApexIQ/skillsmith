"""Skill Quality Metrics System for tracking execution telemetry."""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

class DegradationTrend(Enum):
    """Skill performance trend indicators."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"

@dataclass
class SkillMetrics:
    """Metrics for a single skill."""
    skill_name: str
    version: str
    applied_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    completion_count: int = 0
    fallback_count: int = 0
    total_token_cost: int = 0
    total_execution_time_ms: int = 0
    user_override_count: int = 0
    last_applied: Optional[str] = None
    degradation_trend: str = DegradationTrend.STABLE.value
    quality_score: int = 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.applied_count == 0:
            return 1.0
        return self.success_count / self.applied_count

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate."""
        if self.applied_count == 0:
            return 1.0
        return self.completion_count / self.applied_count

    @property
    def fallback_rate(self) -> float:
        """Calculate fallback rate."""
        if self.applied_count == 0:
            return 0.0
        return self.fallback_count / self.applied_count

    @property
    def avg_token_cost(self) -> int:
        """Calculate average token cost."""
        if self.applied_count == 0:
            return 0
        return int(self.total_token_cost / self.applied_count)

    @property
    def avg_execution_time_ms(self) -> int:
        """Calculate average execution time."""
        if self.applied_count == 0:
            return 0
        return int(self.total_execution_time_ms / self.applied_count)

    @property
    def user_override_rate(self) -> float:
        """Calculate user override rate."""
        if self.applied_count == 0:
            return 0.0
        return self.user_override_count / self.applied_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "skill_name": self.skill_name,
            "version": self.version,
            "metrics": {
                "applied_count": self.applied_count,
                "success_rate": round(self.success_rate, 2),
                "completion_rate": round(self.completion_rate, 2),
                "fallback_rate": round(self.fallback_rate, 2),
                "avg_token_cost": self.avg_token_cost,
                "avg_execution_time_ms": self.avg_execution_time_ms,
                "user_override_rate": round(self.user_override_rate, 2),
                "last_applied": self.last_applied,
                "degradation_trend": self.degradation_trend,
                "quality_score": self.quality_score
            }
        }

class MetricsService:
    """Service for tracking and analyzing skill metrics."""

    def __init__(self, project_root: Path):
        """Initialize metrics service.

        Args:
            project_root: Root directory of the project.
        """
        self.root = project_root
        self.lockfile_path = self.root / "skills.lock.json"
        self.metrics_cache: Dict[str, SkillMetrics] = {}
        self._load_metrics()

    def _load_metrics(self) -> None:
        """Load metrics from lockfile."""
        if not self.lockfile_path.exists():
            return

        try:
            with open(self.lockfile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for skill_name, skill_data in data.get("skills", {}).items():
                if "metrics" in skill_data:
                    metrics_data = skill_data["metrics"]
                    self.metrics_cache[skill_name] = SkillMetrics(
                        skill_name=skill_name,
                        version=skill_data.get("version", "1.0.0"),
                        applied_count=metrics_data.get("applied_count", 0),
                        success_count=int(metrics_data.get("success_rate", 1.0) * metrics_data.get("applied_count", 0)),
                        completion_count=int(metrics_data.get("completion_rate", 1.0) * metrics_data.get("applied_count", 0)),
                        fallback_count=int(metrics_data.get("fallback_rate", 0.0) * metrics_data.get("applied_count", 0)),
                        total_token_cost=metrics_data.get("avg_token_cost", 0) * metrics_data.get("applied_count", 0),
                        total_execution_time_ms=metrics_data.get("avg_execution_time_ms", 0) * metrics_data.get("applied_count", 0),
                        user_override_count=int(metrics_data.get("user_override_rate", 0.0) * metrics_data.get("applied_count", 0)),
                        last_applied=metrics_data.get("last_applied"),
                        degradation_trend=metrics_data.get("degradation_trend", "stable"),
                        quality_score=metrics_data.get("quality_score", 100)
                    )
        except Exception as e:
            # Silently continue if metrics can't be loaded
            pass

    def _save_metrics(self) -> None:
        """Save metrics to lockfile."""
        # Load existing lockfile or create new
        if self.lockfile_path.exists():
            with open(self.lockfile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"skills": {}}

        # Update metrics for each skill
        for skill_name, metrics in self.metrics_cache.items():
            if skill_name not in data["skills"]:
                data["skills"][skill_name] = {}
            data["skills"][skill_name].update(metrics.to_dict())

        # Save updated lockfile
        with open(self.lockfile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def record_execution(
        self,
        skill_name: str,
        success: bool,
        completed: bool,
        used_fallback: bool = False,
        user_override: bool = False,
        token_cost: int = 0,
        execution_time_ms: int = 0
    ) -> None:
        """Record a skill execution event.

        Args:
            skill_name: Name of the skill.
            success: Whether execution was successful.
            completed: Whether execution completed.
            used_fallback: Whether a fallback was used.
            user_override: Whether user overrode the skill.
            token_cost: Token cost of execution.
            execution_time_ms: Execution time in milliseconds.
        """
        if skill_name not in self.metrics_cache:
            self.metrics_cache[skill_name] = SkillMetrics(
                skill_name=skill_name,
                version="1.0.0"
            )

        metrics = self.metrics_cache[skill_name]
        metrics.applied_count += 1
        if success:
            metrics.success_count += 1
        else:
            metrics.failure_count += 1
        if completed:
            metrics.completion_count += 1
        if used_fallback:
            metrics.fallback_count += 1
        if user_override:
            metrics.user_override_count += 1

        metrics.total_token_cost += token_cost
        metrics.total_execution_time_ms += execution_time_ms
        metrics.last_applied = datetime.now().isoformat() + "Z"

        # Update degradation trend
        metrics.degradation_trend = self._calculate_trend(metrics).value

        # Update quality score
        metrics.quality_score = self._calculate_quality_score(metrics)

        # Save immediately
        self._save_metrics()

    def _calculate_trend(self, metrics: SkillMetrics) -> DegradationTrend:
        """Calculate degradation trend for a skill.

        Args:
            metrics: Skill metrics.

        Returns:
            Degradation trend.
        """
        if metrics.applied_count < 5:
            return DegradationTrend.STABLE

        success_rate = metrics.success_rate
        if success_rate < 0.5:
            return DegradationTrend.CRITICAL
        elif success_rate < 0.7:
            return DegradationTrend.DECLINING
        elif success_rate > 0.9:
            return DegradationTrend.IMPROVING
        else:
            return DegradationTrend.STABLE

    def _calculate_quality_score(self, metrics: SkillMetrics) -> int:
        """Calculate quality score for a skill.

        Args:
            metrics: Skill metrics.

        Returns:
            Quality score (0-100).
        """
        if metrics.applied_count == 0:
            return 100

        # Weighted scoring
        success_weight = 40
        completion_weight = 30
        fallback_weight = -20
        override_weight = -10

        score = (
            metrics.success_rate * success_weight +
            metrics.completion_rate * completion_weight +
            (1 - metrics.fallback_rate) * abs(fallback_weight) +
            (1 - metrics.user_override_rate) * abs(override_weight)
        )

        return max(0, min(100, int(score)))

    def get_metrics(self, skill_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a skill or all skills.

        Args:
            skill_name: Optional skill name. If None, return all metrics.

        Returns:
            Metrics dictionary.
        """
        if skill_name:
            if skill_name in self.metrics_cache:
                return self.metrics_cache[skill_name].to_dict()
            else:
                return {"error": f"No metrics found for skill: {skill_name}"}
        else:
            return {
                "skills": {
                    name: metrics.to_dict()
                    for name, metrics in self.metrics_cache.items()
                }
            }

    def get_degraded_skills(self, threshold: float = 0.7) -> List[str]:
        """Get list of degraded skills.

        Args:
            threshold: Success rate threshold below which skill is considered degraded.

        Returns:
            List of degraded skill names.
        """
        degraded = []
        for skill_name, metrics in self.metrics_cache.items():
            if metrics.success_rate < threshold or metrics.degradation_trend in ["declining", "critical"]:
                degraded.append(skill_name)
        return degraded

    def get_top_performers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing skills.

        Args:
            limit: Number of top skills to return.

        Returns:
            List of top performing skills with metrics.
        """
        sorted_skills = sorted(
            self.metrics_cache.items(),
            key=lambda x: x[1].quality_score,
            reverse=True
        )

        return [
            metrics.to_dict()
            for _, metrics in sorted_skills[:limit]
        ]

    def export_metrics(self, format: str = "json") -> str:
        """Export all metrics in specified format.

        Args:
            format: Export format (json, csv, markdown).

        Returns:
            Exported metrics as string.
        """
        all_metrics = self.get_metrics()

        if format == "json":
            return json.dumps(all_metrics, indent=2)
        elif format == "csv":
            # Simple CSV export
            lines = ["skill_name,version,applied_count,success_rate,quality_score"]
            for skill_name, metrics in self.metrics_cache.items():
                lines.append(
                    f"{skill_name},{metrics.version},{metrics.applied_count},"
                    f"{metrics.success_rate:.2f},{metrics.quality_score}"
                )
            return "\n".join(lines)
        elif format == "markdown":
            # Markdown table export
            lines = [
                "| Skill | Version | Applied | Success Rate | Quality |",
                "|-------|---------|---------|--------------|---------|"
            ]
            for skill_name, metrics in self.metrics_cache.items():
                lines.append(
                    f"| {skill_name} | {metrics.version} | {metrics.applied_count} | "
                    f"{metrics.success_rate:.2%} | {metrics.quality_score}/100 |"
                )
            return "\n".join(lines)
        else:
            return json.dumps(all_metrics, indent=2)