"""Evolution Engine Core - FIX, DERIVE, and CAPTURE modes for autonomous skill evolution."""

import json
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import yaml
import re

class EvolutionMode(Enum):
    """Evolution operation modes."""
    FIX = "fix"          # Auto-repair degraded skills
    DERIVE = "derive"    # Create specialized versions
    CAPTURE = "capture"  # Extract from execution history

class DegradationLevel(Enum):
    """Skill degradation severity levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"

@dataclass
class EvolutionCandidate:
    """Represents a skill candidate for evolution."""
    name: str
    path: Path
    mode: EvolutionMode
    metrics: Dict[str, Any]
    degradation_level: DegradationLevel
    reason: str
    priority: int  # 1-10, higher is more urgent

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "mode": self.mode.value,
            "metrics": self.metrics,
            "degradation_level": self.degradation_level.value,
            "reason": self.reason,
            "priority": self.priority
        }

@dataclass
class EvolutionResult:
    """Result of an evolution analysis (the Handoff Packet)."""
    success: bool
    skill_name: str
    mode: EvolutionMode
    original_version: str
    proposed_version: str
    changes_suggested: List[str]
    context_packet: Dict[str, Any]  # The data the agent needs to perform the edit
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for agent consumption."""
        return {
            "success": self.success,
            "skill_name": self.skill_name,
            "mode": self.mode.value,
            "original_version": self.original_version,
            "proposed_version": self.proposed_version,
            "changes_suggested": self.changes_suggested,
            "context_packet": self.context_packet,
            "error": self.error,
            "timestamp": datetime.now().isoformat() + "Z"
        }

class EvolutionEngine:
    """Core evolution engine for autonomous skill improvement."""

    def __init__(self, project_root: Path):
        """Initialize evolution engine.

        Args:
            project_root: Root directory of the project.
        """
        self.root = project_root
        self.agent_dir = self.root / ".agent"
        self.skills_dir = self.agent_dir / "skills"
        self.versions_dir = self.agent_dir / "versions"
        self.evolution_log = self.agent_dir / "evolution.jsonl"
        self.lockfile_path = self.root / "skills.lock.json"

        # Safety limits
        self.max_evolution_depth = 3  # Max recursive evolutions
        self.min_evolution_interval = 3600  # Min seconds between evolutions
        self.evolution_history: Dict[str, List[float]] = {}  # Track evolution timestamps

        # Create directories
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def analyze_skills(self, threshold: float = 0.7) -> List[EvolutionCandidate]:
        """Analyze all skills and identify evolution candidates.

        Args:
            threshold: Success rate threshold for degradation detection.

        Returns:
            List of evolution candidates sorted by priority.
        """
        candidates = []

        # Load lockfile for metrics
        if not self.lockfile_path.exists():
            return candidates

        with open(self.lockfile_path, 'r', encoding='utf-8') as f:
            lockfile = json.load(f)

        skills_list = lockfile.get("skills", [])

        # Convert list to dict if needed
        if isinstance(skills_list, list):
            skills = {skill.get("name", f"skill_{i}"): skill for i, skill in enumerate(skills_list)}
        else:
            skills = skills_list

        for skill_name, skill_data in skills.items():
            skill_path = self.skills_dir / skill_name
            if not skill_path.exists():
                continue

            metrics = skill_data.get("metrics", {})

            # Analyze degradation
            level, reason = self._assess_degradation(metrics)

            if level in [DegradationLevel.DEGRADED, DegradationLevel.CRITICAL, DegradationLevel.FAILED]:
                # Candidate for FIX mode
                candidates.append(EvolutionCandidate(
                    name=skill_name,
                    path=skill_path,
                    mode=EvolutionMode.FIX,
                    metrics=metrics,
                    degradation_level=level,
                    reason=reason,
                    priority=self._calculate_priority(level, metrics)
                ))
            elif metrics.get("applied_count", 0) > 10:
                # Check for specialization opportunities
                if self._needs_specialization(skill_name, metrics):
                    candidates.append(EvolutionCandidate(
                        name=skill_name,
                        path=skill_path,
                        mode=EvolutionMode.DERIVE,
                        metrics=metrics,
                        degradation_level=DegradationLevel.HEALTHY,
                        reason="High usage with context variations detected",
                        priority=5
                    ))

        return sorted(candidates, key=lambda x: x.priority, reverse=True)

    def trigger_evolution_from_metrics(self, summary_metrics: Dict[str, Any]) -> List[Path]:
        """Trigger evolution based on summary metrics (e.g. from an eval run).
        
        Args:
            summary_metrics: Dictionary containing 'tacr' and potentially other summary signals.
            
        Returns:
            Paths to generated handoff packets.
        """
        # Threshold calculation: if TACR is low, we are more aggressive in identifying candidates
        threshold = summary_metrics.get("tacr", 75.0) / 100.0
        candidates = self.analyze_skills(threshold=threshold)
        
        handoff_packets = []
        handoff_dir = self.agent_dir / "handoffs"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        for candidate in candidates:
            if candidate.mode == EvolutionMode.FIX:
                if not self.check_safety(candidate.name):
                    continue
                    
                result = self.prepare_repair_plan(candidate)
                if result.success:
                    packet_path = handoff_dir / f"evolution_repair_{candidate.name}.json"
                    packet_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
                    handoff_packets.append(packet_path)
                    self.record_evolution(candidate.name)
                    self._log_evolution(result)
        
        return handoff_packets

    def apply_repair(self, skill_name: str, repair_packet: Dict[str, Any]) -> bool:
        """Apply a repair packet to a skill. 
        Note: This is a basic implementation that increments version and logs context.
        Full logic repair requires an LLM-based agent.
        """
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        
        if not skill_md.exists():
            return False
            
        # Implementation of "Active Repair" for autonomous loops:
        # We append the evolution metadata to the SKILL.md so the executor can 'see' the repair context
        try:
            current_content = skill_md.read_text(encoding="utf-8")
            
            # Backup original
            original_version = repair_packet.get("original_version", "1.0.0")
            self._backup_skill(skill_path, original_version)
            
            # Prepare evolution breadcrumb
            breadcrumb = f"\n\n## Evolution Log (v{repair_packet.get('proposed_version')})\n"
            breadcrumb += f"- **Mode**: {repair_packet.get('mode')}\n"
            breadcrumb += f"- **Date**: {datetime.now().isoformat()}Z\n"
            breadcrumb += "- **Suggested Changes**:\n"
            for change in repair_packet.get("changes_suggested", []):
                breadcrumb += f"  - {change}\n"
            breadcrumb += f"- **Context**: {repair_packet.get('context_packet', {}).get('failure_reason', 'Regression detected in benchmark')}\n"
            
            # Update content
            new_content = current_content + breadcrumb
            skill_md.write_text(new_content, encoding="utf-8")
            
            # Record it
            self.record_evolution(skill_name)
            return True
        except Exception:
            return False

    def _assess_degradation(self, metrics: Dict[str, Any]) -> Tuple[DegradationLevel, str]:
        """Assess degradation level of a skill.

        Args:
            metrics: Skill metrics dictionary.

        Returns:
            Tuple of (degradation level, reason).
        """
        success_rate = metrics.get("success_rate", 1.0)
        applied_count = metrics.get("applied_count", 0)
        failure_count = metrics.get("failure_count", 0)
        fallback_rate = metrics.get("fallback_rate", 0.0)
        user_override_rate = metrics.get("user_override_rate", 0.0)

        # No data - assume healthy
        if applied_count == 0:
            return DegradationLevel.HEALTHY, "No usage data"

        # Critical failures
        if success_rate < 0.3:
            return DegradationLevel.FAILED, f"Critical failure rate: {(1-success_rate)*100:.1f}%"
        elif success_rate < 0.5:
            return DegradationLevel.CRITICAL, f"High failure rate: {(1-success_rate)*100:.1f}%"
        elif success_rate < 0.7:
            return DegradationLevel.DEGRADED, f"Elevated failure rate: {(1-success_rate)*100:.1f}%"
        elif user_override_rate > 0.3:
            return DegradationLevel.DEGRADED, f"High user override rate: {user_override_rate*100:.1f}%"
        elif fallback_rate > 0.4:
            return DegradationLevel.WARNING, f"High fallback rate: {fallback_rate*100:.1f}%"
        else:
            return DegradationLevel.HEALTHY, "Performing well"

    def _calculate_priority(self, level: DegradationLevel, metrics: Dict[str, Any]) -> int:
        """Calculate evolution priority.

        Args:
            level: Degradation level.
            metrics: Skill metrics.

        Returns:
            Priority score (1-10).
        """
        base_priority = {
            DegradationLevel.FAILED: 10,
            DegradationLevel.CRITICAL: 8,
            DegradationLevel.DEGRADED: 6,
            DegradationLevel.WARNING: 4,
            DegradationLevel.HEALTHY: 2
        }.get(level, 1)

        # Adjust based on usage
        applied_count = metrics.get("applied_count", 0)
        if applied_count > 100:
            base_priority = min(10, base_priority + 2)
        elif applied_count > 50:
            base_priority = min(10, base_priority + 1)

        return base_priority

    def _needs_specialization(self, skill_name: str, metrics: Dict[str, Any]) -> bool:
        """Check if a skill needs specialization.

        Args:
            skill_name: Name of the skill.
            metrics: Skill metrics.

        Returns:
            True if specialization is recommended.
        """
        # Check for high variance in execution contexts
        success_rate = metrics.get("success_rate", 1.0)
        applied_count = metrics.get("applied_count", 0)

        # If success varies significantly (would need context tracking)
        # For now, simple heuristic
        if applied_count > 20 and 0.6 < success_rate < 0.85:
            return True

        return False

    def prepare_repair_plan(self, candidate: EvolutionCandidate) -> EvolutionResult:
        """Analyze a degraded skill and prepare a Repair Plan for the Agent.

        Args:
            candidate: Evolution candidate.

        Returns:
            Evolution result containing the repair context.
        """
        skill_path = candidate.path
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return EvolutionResult(
                success=False, skill_name=candidate.name, mode=EvolutionMode.FIX,
                original_version="unknown", proposed_version="unknown",
                changes_suggested=[], context_packet={}, error="SKILL.md not found"
            )

        content = skill_md.read_text(encoding="utf-8")
        
        # Determine suggested changes based on metrics
        changes = []
        if candidate.degradation_level in [DegradationLevel.CRITICAL, DegradationLevel.FAILED]:
            changes.append("Integrate formal Error Recovery Patterns")
        if candidate.metrics.get("failure_count", 0) > 3:
            changes.append("Add automated Validation Rules for pre-execution")
        if candidate.metrics.get("user_override_rate", 0) > 0.2:
            changes.append("Clarify ambiguous instructions to reduce user overrides")

        # Create the Handoff Packet
        return EvolutionResult(
            success=True,
            skill_name=candidate.name,
            mode=EvolutionMode.FIX,
            original_version=candidate.metrics.get("version", "1.0.0"),
            proposed_version=self._increment_version(candidate.metrics.get("version", "1.0.0")),
            changes_suggested=changes,
            context_packet={
                "current_content": content,
                "metrics": candidate.metrics,
                "failure_reason": candidate.reason,
                "target_file": str(skill_md)
            }
        )

    def prepare_derivation_spec(self, candidate: EvolutionCandidate, context: str) -> EvolutionResult:
        """Prepare a Derivation Specification for the Agent.

        Args:
            candidate: Evolution candidate.
            context: Specialization context (e.g., "fastapi").

        Returns:
            Evolution result containing the derivation context.
        """
        skill_path = candidate.path
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return EvolutionResult(
                success=False, skill_name=candidate.name, mode=EvolutionMode.DERIVE,
                original_version="unknown", proposed_version="1.0.0",
                changes_suggested=[], context_packet={}, error="SKILL.md not found"
            )

        content = skill_md.read_text(encoding="utf-8")

        # Handoff to Agent: Provide the original + the goal
        return EvolutionResult(
            success=True,
            skill_name=f"{candidate.name}_{context}",
            mode=EvolutionMode.DERIVE,
            original_version=candidate.metrics.get("version", "1.0.0"),
            proposed_version="1.0.0",
            changes_suggested=[f"Specialize for {context} architecture", f"Apply {context} best practices"],
            context_packet={
                "parent_skill": candidate.name,
                "parent_content": content,
                "specialization_context": context,
                "target_directory": str(self.skills_dir / f"{candidate.name}_{context}")
            }
        )

    def _increment_version(self, version: str, bump_type: str = "patch") -> str:
        """Increment semantic version.

        Args:
            version: Current version string.
            bump_type: Type of version bump (major, minor, patch).

        Returns:
            Incremented version string.
        """
        parts = version.split(".")
        if len(parts) != 3:
            return "1.0.1"

        try:
            major, minor, patch = map(int, parts)
        except:
            return "1.0.1"

        if bump_type == "major":
            return f"{major + 1}.0.0"
        elif bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        else:  # patch
            return f"{major}.{minor}.{patch + 1}"

    def _backup_skill(self, skill_path: Path, version: str) -> None:
        """Create a backup of a skill before evolution.

        Args:
            skill_path: Path to the skill.
            version: Version to backup.
        """
        skill_name = skill_path.name
        version_dir = self.versions_dir / skill_name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files
        for file in skill_path.glob("*"):
            if file.is_file():
                dest = version_dir / file.name
                dest.write_bytes(file.read_bytes())

        # Add backup metadata
        backup_meta = {
            "skill_name": skill_name,
            "version": version,
            "backed_up_at": datetime.now().isoformat() + "Z",
            "original_path": str(skill_path)
        }
        (version_dir / "backup.json").write_text(json.dumps(backup_meta, indent=2), encoding="utf-8")

    def _log_evolution(self, result: EvolutionResult) -> None:
        """Log evolution result.

        Args:
            result: Evolution result to log.
        """
        with open(self.evolution_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

    def check_safety(self, skill_name: str) -> bool:
        """Check if it's safe to evolve a skill.

        Args:
            skill_name: Name of the skill.

        Returns:
            True if safe to evolve.
        """
        # Check evolution history
        if skill_name in self.evolution_history:
            last_evolution = self.evolution_history[skill_name][-1]
            if time.time() - last_evolution < self.min_evolution_interval:
                return False

            # Check for too many recent evolutions
            recent_evolutions = [t for t in self.evolution_history[skill_name]
                                if time.time() - t < 86400]  # Last 24 hours
            if len(recent_evolutions) >= self.max_evolution_depth:
                return False

        return True

    def record_evolution(self, skill_name: str) -> None:
        """Record that a skill was evolved.

        Args:
            skill_name: Name of the skill.
        """
        if skill_name not in self.evolution_history:
            self.evolution_history[skill_name] = []
        self.evolution_history[skill_name].append(time.time())

    def get_evolution_history(self) -> List[Dict[str, Any]]:
        """Get complete evolution history.

        Returns:
            List of evolution records.
        """
        if not self.evolution_log.exists():
            return []

        history = []
        with open(self.evolution_log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    history.append(json.loads(line))
                except:
                    continue

        return history