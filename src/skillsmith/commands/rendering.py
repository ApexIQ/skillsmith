from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from .lockfile import (
    _normalize_publisher_key_rotation,
    _normalize_publisher_keys,
    _normalize_publisher_public_keys,
    _publisher_signature_algorithms,
)
from .workflow_engine import build_workflow, workflow_bundle_definitions, workflow_markdown


def _list_or_default(values: list[str], fallback: str = "not-specified") -> str:
    cleaned = [value for value in values if value and value != "none"]
    return ", ".join(cleaned) if cleaned else fallback


def _publisher_key_ids(profile: dict) -> str:
    return _list_or_default(list(_normalize_publisher_keys(profile.get("trusted_publisher_keys", {})).keys()), "none")


def _publisher_public_key_ids(profile: dict) -> str:
    return _list_or_default(list(_normalize_publisher_public_keys(profile.get("trusted_publisher_public_keys", {})).keys()), "none")


def _key_rotation_summary(profile: dict) -> str:
    rotation = _normalize_publisher_key_rotation(profile.get("publisher_key_rotation", {}))
    if not rotation:
        return "none"
    parts = []
    if rotation.get("current_key_id"):
        parts.append(f"current={rotation['current_key_id']}")
    if rotation.get("previous_key_ids"):
        parts.append(f"previous={','.join(rotation['previous_key_ids'])}")
    if rotation.get("rotation_grace_period_days") is not None:
        parts.append(f"grace={rotation['rotation_grace_period_days']}")
    if rotation.get("rotated_at"):
        parts.append(f"rotated_at={rotation['rotated_at']}")
    return " ".join(parts) if parts else "none"


def load_project_profile(cwd: Path) -> dict:
    profile_path = cwd / ".agent" / "project_profile.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Project profile not found at {profile_path}")
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def selected_tools(profile: dict) -> set[str]:
    tools = {tool.strip().lower() for tool in profile.get("target_tools", []) if tool}
    return tools or {"codex", "claude"}


def render_agents_md(profile: dict) -> str:
    return f"""# AGENTS.md

> Primary project instructions for AI coding agents.

## Prime Directives

1. Read `.agent/STATE.md` first.
2. Read `.agent/project_profile.yaml` and `.agent/context/project-context.md` before making stack assumptions.
3. Search `.agent/skills/` for the most relevant instructions before implementation.
4. Follow the Discuss -> Plan -> Execute -> Verify loop.
5. Update `.agent/STATE.md` after significant steps.

## Execution Standard

- Plan first for non-trivial work (3+ steps, architecture changes, migrations, or risky edits).
- Keep fixes minimal and focused. Avoid broad refactors unless required for correctness.
- Delegate to subagents only for parallelizable or clearly specialized tasks.
- One owner per subtask; merge results only after verification.
- Never mark done without evidence (tests, command output, or concrete behavioral checks).

## Memory and Cost Policy (Library-First)

- Optimize for `pip install skillsmith` local workflows first; external services remain optional.
- Prefer retrieval reuse and cheap context operations before model-heavy loops.
- Apply the five-layer memory pattern in order:
  1. observer capture
  2. reflector compaction
  3. session recovery
  4. reactive watcher refresh
  5. pre-compaction safeguard
- Require TTL + fingerprint invalidation for recall-cache reuse.
- Do not introduce mandatory hosted infra for core success paths.

## Role Playbook

- `orchestrator`: owns problem framing, execution sequencing, and delegation boundaries.
- `researcher`: gathers repo context, constraints, and references before edits begin.
- `implementer`: applies minimal, testable changes aligned with the agreed plan.
- `reviewer`: validates correctness and regressions; reports findings before summaries.

## Handoff Contract

- Every handoff should include: goal, scope, changed files, risks, and verification evidence.
- `researcher -> implementer`: concrete constraints, touched code areas, and edge cases.
- `implementer -> reviewer`: diff summary, test output, and known limitations.
- `reviewer -> orchestrator`: severity-ordered findings and release recommendation.

## Quality Gates

- Correctness: prove the change solves the requested problem.
- Safety: avoid regressions and preserve existing behavior unless intentionally changed.
- Verification: run the closest relevant tests/checks before completion.
- Explainability: provide a concise change summary and why it is safe.

## Project Profile

- Idea: {profile.get("idea", "not-specified")}
- Stage: {profile.get("project_stage", "not-specified")}
- App type: {profile.get("app_type", "not-specified")}
- Languages: {_list_or_default(profile.get("languages", []))}
- Frameworks: {_list_or_default(profile.get("frameworks", []), "none-detected")}
- Package manager: {profile.get("package_manager", "not-specified")}
- Deployment target: {profile.get("deployment_target", "not-specified")}
- Priorities: {_list_or_default(profile.get("priorities", []))}
- Target tools: {_list_or_default(profile.get("target_tools", []))}
- Trusted skill sources: {_list_or_default(profile.get("trusted_skill_sources", []), "local")}
- Allowed remote domains: {_list_or_default(profile.get("allowed_remote_domains", []), "github.com, skills.sh")}
- Require pinned GitHub refs: {"true" if profile.get("require_pinned_github_refs", True) else "false"}
- Trusted publisher keys: {_publisher_key_ids(profile)}
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher verification mode: {profile.get("publisher_verification_mode", "optional")}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
- Allowed publisher signature algorithms: {", ".join(_publisher_signature_algorithms(profile.get("publisher_signature_algorithms", [])))}
- Publisher key rotation: {_key_rotation_summary(profile)}
- Minimum remote trust: {profile.get("min_remote_trust_score", 65)}

## Project Structure

- `.agent/PROJECT.md`: rendered project vision and architecture
- `.agent/ROADMAP.md`: rendered milestones and next moves
- `.agent/STATE.md`: current tactical state
- `.agent/project_profile.yaml`: structured source of truth
- `.agent/context/project-context.md`: generated repo context
- `.agent/skills/`: reusable procedural skills
- `.agent/workflows/`: internal workflow source layer
"""


def render_project_md(profile: dict) -> str:
    return f"""# Project Overview

## Vision
{profile.get("idea", "Project using skillsmith")}

## Tech Stack
- Languages: {_list_or_default(profile.get("languages", []))}
- Frameworks: {_list_or_default(profile.get("frameworks", []), "none-detected")}
- Package manager: {profile.get("package_manager", "not-specified")}
- Deployment: {profile.get("deployment_target", "not-specified")}
- Trusted skill sources: {_list_or_default(profile.get("trusted_skill_sources", []), "local")}
- Allowed remote domains: {_list_or_default(profile.get("allowed_remote_domains", []), "github.com, skills.sh")}
- Require pinned GitHub refs: {"true" if profile.get("require_pinned_github_refs", True) else "false"}
- Trusted publisher keys: {_publisher_key_ids(profile)}
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher verification mode: {profile.get("publisher_verification_mode", "optional")}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
- Allowed publisher signature algorithms: {", ".join(_publisher_signature_algorithms(profile.get("publisher_signature_algorithms", [])))}
- Publisher key rotation: {_key_rotation_summary(profile)}
- Minimum remote trust: {profile.get("min_remote_trust_score", 65)}

## Architecture
- App type: {profile.get("app_type", "not-specified")}
- Stage: {profile.get("project_stage", "not-specified")}
- Generated from `.agent/project_profile.yaml`

## Priorities
""" + "\n".join(f"- {priority}" for priority in profile.get("priorities", []))


def render_roadmap_md(profile: dict) -> str:
    priorities = profile.get("priorities", []) or ["maintainability", "verification"]
    tools = profile.get("target_tools", []) or ["codex", "claude"]
    return f"""# Roadmap

## Milestone 1: Foundation
- [ ] Align generated instructions from `.agent/project_profile.yaml`
- [ ] Validate native paths for: {_list_or_default(tools)}
- [ ] Confirm build/test commands from generated context

## Milestone 2: Workflow Quality
- [ ] Improve workflow packs for {_list_or_default(profile.get("frameworks", []), "the current stack")}
- [ ] Add profile-aware skill discovery and ranking
- [ ] Strengthen doctor/path validation

## Milestone 3: Product Differentiation
- [ ] Guided setup refinements around priorities: {_list_or_default(priorities)}
- [ ] Remote registry federation and trust scoring
- [ ] Continuous alignment and drift detection
"""


def render_state_md(profile: dict) -> str:
    today = datetime.date.today().isoformat()
    return f"""# Current State

> **CRITICAL**: AI agents MUST read this file at the start of every session.
> Update this file after every significant step to prevent context rot.

**Last Updated:** {today}

## Current Objective
Keep project instructions, rules, and workflows aligned with `.agent/project_profile.yaml`.

## Context
- Idea: {profile.get("idea", "not-specified")}
- Stage: {profile.get("project_stage", "not-specified")}
- Frameworks: {_list_or_default(profile.get("frameworks", []), "none-detected")}
- Target tools: {_list_or_default(profile.get("target_tools", []))}
- Trusted skill sources: {_list_or_default(profile.get("trusted_skill_sources", []), "local")}
- Allowed remote domains: {_list_or_default(profile.get("allowed_remote_domains", []), "github.com, skills.sh")}
- Require pinned GitHub refs: {"true" if profile.get("require_pinned_github_refs", True) else "false"}
- Trusted publisher keys: {_publisher_key_ids(profile)}
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher verification mode: {profile.get("publisher_verification_mode", "optional")}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
- Allowed publisher signature algorithms: {", ".join(_publisher_signature_algorithms(profile.get("publisher_signature_algorithms", [])))}
- Publisher key rotation: {_key_rotation_summary(profile)}
- Minimum remote trust: {profile.get("min_remote_trust_score", 65)}

## Recent Changes
- Generated or aligned project instructions from the saved profile.

## Next Steps
1. Update the profile when project assumptions change.
2. Run `skillsmith align` to re-render managed files.
3. Verify generated paths with `skillsmith doctor`.

## Known Issues
None recorded.
"""


def render_claude_md(profile: dict) -> str:
    return f"""# CLAUDE.md

## Context
- Read `AGENTS.md` first.
- Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.
- Project idea: {profile.get("idea", "not-specified")}
- Target stack: {_list_or_default(profile.get("frameworks", []), _list_or_default(profile.get("languages", [])))}
- Trusted remote sources: {_list_or_default(profile.get("trusted_skill_sources", []), "local")}
- Allowed remote domains: {_list_or_default(profile.get("allowed_remote_domains", []), "github.com, skills.sh")}
- Require pinned GitHub refs: {"true" if profile.get("require_pinned_github_refs", True) else "false"}
- Trusted publisher keys: {_publisher_key_ids(profile)}
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher verification mode: {profile.get("publisher_verification_mode", "optional")}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
- Allowed publisher signature algorithms: {", ".join(_publisher_signature_algorithms(profile.get("publisher_signature_algorithms", [])))}
- Publisher key rotation: {_key_rotation_summary(profile)}

## Workflow Protocol

1. Discuss: confirm intent, constraints, and edge cases.
2. Plan: required for non-trivial work; include verification steps.
3. Execute: make focused, reversible edits with clear ownership.
4. Verify: run tests/checks and confirm observed behavior.
5. Report: summarize changes, risks, and evidence.

## Delegation Policy

- Use `.claude/agents/` when specialization or parallel execution materially helps.
- Do not delegate urgent blocking work that can be completed directly.
- Keep one clear subtask per subagent and avoid overlapping write scope.

## Memory and Cost Policy

- Keep the default path library-first: `pip install skillsmith` is sufficient.
- Reuse cached retrieval context before expensive reasoning passes.
- Follow five layers: observer, reflector, session recovery, reactive watcher, pre-compaction safeguard.
- Use TTL + fingerprint invalidation for cache reuse.
- Keep enterprise infrastructure optional for non-enterprise users.

## Role Use

- `orchestrator`: set plan, assign role ownership, and gate completion.
- `researcher`: gather constraints and evidence before implementation starts.
- `implementer`: make focused edits and provide verification artifacts.
- `reviewer`: produce findings-first validation and regression checks.

## Role Handoff

- Include goal, scope, file list, verification run, and unresolved risks in each handoff.
- Prefer `researcher -> implementer -> reviewer -> orchestrator` for non-trivial tasks.

## Completion Bar

- Keep work aligned with `.agent/PROJECT.md` and `.agent/ROADMAP.md`.
- Do not claim completion without concrete verification evidence.
- Prefer the simplest correct solution over clever complexity.
"""


def render_gemini_md(profile: dict) -> str:
    return f"""# GEMINI.md

## Prime Directives
1. Read `AGENTS.md`.
2. Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.
3. Search `.agent/skills/` before implementation.
4. Follow Discuss -> Plan -> Execute -> Verify.

## Execution Policy
- Plan before coding for non-trivial work (3+ steps or architectural impact).
- Keep changes minimal, explicit, and easy to verify.
- Use subagents only when parallelism or specialization is clearly beneficial.
- Verify with tests/checks before marking done.

## Memory and Cost Policy
- Preserve a library-first default path with no mandatory hosted infra.
- Prefer retrieval reuse and cheap context operations before model-heavy loops.
- Use the five-layer memory reliability pattern:
  1. observer capture
  2. reflector compaction
  3. session recovery
  4. reactive watcher refresh
  5. pre-compaction safeguard
- Cache reuse must be guarded by TTL and context/policy fingerprints.

## Role Use
- `orchestrator`: own task framing, delegation decisions, and final readiness.
- `researcher`: collect repository facts, constraints, and edge cases first.
- `implementer`: apply minimal code changes with verification evidence.
- `reviewer`: perform findings-first checks for correctness and regressions.

## Role Handoff
- Pass goal, scope, file list, risks, and verification evidence between roles.
- Prefer `researcher -> implementer -> reviewer -> orchestrator` for non-trivial work.

## Project Summary
- Idea: {profile.get("idea", "not-specified")}
- Languages: {_list_or_default(profile.get("languages", []))}
- Frameworks: {_list_or_default(profile.get("frameworks", []), "none-detected")}
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}

## Quick References
- `.agent/PROJECT.md` for architecture and direction.
- `.agent/ROADMAP.md` for milestone priorities.
- `.agent/workflows/` for reusable runbooks.
"""


def render_copilot_md(profile: dict) -> str:
    return f"""# GitHub Copilot Instructions

## Project Overview
- Idea: {profile.get("idea", "not-specified")}
- Stage: {profile.get("project_stage", "not-specified")}
- Stack: {_list_or_default(profile.get("frameworks", []), _list_or_default(profile.get("languages", [])))}

## Required Context
- `AGENTS.md`
- `.agent/STATE.md`
- `.agent/project_profile.yaml`
- `.agent/context/project-context.md`
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}

## Workflow
- Search `.agent/skills/` for relevant task guidance.
- Use `.agent/workflows/` and tool-native commands for repeatable flows.
- Verify before claiming completion.
"""


def render_windsurf_rule(profile: dict) -> str:
    return f"""# Skillsmith Rules

- Read `AGENTS.md` and `.agent/STATE.md`.
- Read `.agent/project_profile.yaml` and `.agent/context/project-context.md`.
- Current focus: {profile.get("idea", "not-specified")}
- Prefer relevant skills from `.agent/skills/` over ad hoc instructions.
- Use `.agent/workflows/` for reusable runbooks like `brainstorm`, `plan-feature`, `debug-issue`, and `test-changes`.
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
- Verify build/test behavior before claiming success.
"""


def render_zencoder_rule(profile: dict) -> str:
    return f"""# Skillsmith Rules

- Use `AGENTS.md` as the portable project instruction file.
- Read `.agent/project_profile.yaml` and `.agent/context/project-context.md`.
- Stack summary: {_list_or_default(profile.get("frameworks", []), _list_or_default(profile.get("languages", [])))}
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
- Keep work aligned with `.agent/PROJECT.md`, `.agent/ROADMAP.md`, and `.agent/STATE.md`.
- Use `.agent/workflows/` when a task matches an existing repeatable workflow bundle.
"""


def render_cursor_rule(profile: dict) -> str:
    return f"""---
description: Skillsmith rules for the current project
globs:
alwaysApply: true
---

- Read `AGENTS.md`, `.agent/STATE.md`, and `.agent/project_profile.yaml`.
- Current focus: {profile.get("idea", "not-specified")}
- Check `.agent/context/project-context.md` before making stack assumptions.
- Prefer relevant skills from `.agent/skills/` before implementation.
- For repeatable flows, use the generated workflow rules in `.cursor/rules/workflows/`.
- Trusted publisher public keys: {_publisher_public_key_ids(profile)}
"""


def render_legacy_cursor_rules(profile: dict) -> str:
    return f"""<!-- Skillsmith -->
# Cursor Rules

- Read `AGENTS.md` and `.agent/STATE.md`.
- Project idea: {profile.get("idea", "not-specified")}
- Generated context: `.agent/context/project-context.md`
- Publisher key rotation: {_key_rotation_summary(profile)}
"""


def render_legacy_windsurf_rules(profile: dict) -> str:
    return f"""<!-- Skillsmith -->
# Windsurf Rules

- Read `AGENTS.md` and `.agent/STATE.md`.
- Project idea: {profile.get("idea", "not-specified")}
- Prefer `.windsurf/rules/skillsmith.md` for the canonical tool-native rule file.
- Publisher signature scheme mode: {profile.get("publisher_signature_scheme_mode", "auto")}
"""


def render_windsurf_workflow(name: str, workflow: dict) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(workflow["steps"], start=1))
    return f"""# Workflow: {name}

## Summary
- Goal: {workflow['goal']}
- Project idea: {workflow['profile']['idea']}
- Skills: {', '.join(workflow['skills']) if workflow['skills'] else 'none'}

## Steps
{steps}
"""


def render_cursor_workflow_rule(name: str, workflow: dict) -> str:
    return f"""---
description: Run the {name} workflow for this project
globs:
alwaysApply: false
---

- Read `.agent/workflows/{name}.md`.
- Goal: {workflow['goal']}
- Skills: {', '.join(workflow['skills']) if workflow['skills'] else 'none'}
- Follow the workflow steps, then verify with project tests or the closest validation command.
"""


def render_zencoder_workflow_rule(name: str, workflow: dict) -> str:
    return f"""# Workflow Rule: {name}

- Read `.agent/workflows/{name}.md`.
- Goal: {workflow['goal']}
- Prefer these skills when relevant: {', '.join(workflow['skills']) if workflow['skills'] else 'none'}
- Complete the workflow with evidence, not assumptions.
"""


def render_claude_agent(role: str, profile: dict) -> str:
    descriptions = {
        "orchestrator": "Coordinate research, implementation, and review using the saved project profile.",
        "researcher": "Gather repo context, relevant skills, and source references before implementation.",
        "implementer": "Make focused code changes that match the project profile and verification bar.",
        "reviewer": "Review correctness, regressions, and missing verification before completion.",
    }
    body = {
        "orchestrator": [
            "- Read `CLAUDE.md`, `.agent/STATE.md`, and `.agent/project_profile.yaml` first.",
            "- Break work into verified steps and route to other subagents when specialization helps.",
        ],
        "researcher": [
            "- Read `.agent/context/project-context.md` before exploring files.",
            "- Identify the most relevant skills and repo areas for the task.",
        ],
        "implementer": [
            "- Use `.agent/project_profile.yaml` and `.agent/context/project-context.md` as the source of truth.",
            "- Leave a concise summary and verification notes for review.",
        ],
        "reviewer": [
            "- Prioritize bugs, regressions, and missing tests.",
            "- Require evidence before accepting a claimed fix.",
        ],
    }
    return f"""---
name: {role}
description: {descriptions[role]}
---

# {role.title()}

## Project Summary
- Idea: {profile.get("idea", "not-specified")}
- Stack: {_list_or_default(profile.get("frameworks", []), _list_or_default(profile.get("languages", [])))}

## Instructions
""" + "\n".join(body[role])


def render_claude_command(name: str) -> str:
    commands = {
        "brainstorm": [
            "Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.",
            "Ask the `researcher` subagent for constraints, repo context, and relevant skills.",
            "Return 2-3 approaches, then recommend one with tradeoffs.",
        ],
        "plan-feature": [
            "Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.",
            "Ask the `researcher` subagent for repo context and relevant skills.",
            "Produce a short plan with verification steps.",
        ],
        "implement-feature": [
            "Read `.agent/STATE.md` and `.agent/project_profile.yaml`.",
            "Ask the `implementer` subagent to make the change.",
            "Ask the `reviewer` subagent to review the result and verification.",
        ],
        "review-changes": [
            "Read `.agent/STATE.md` and `.agent/context/project-context.md`.",
            "Ask the `reviewer` subagent to inspect the current changes.",
            "Return findings first, then a short summary.",
        ],
        "test-changes": [
            "Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.",
            "Ask the `implementer` or `reviewer` subagent to identify the right validation surface.",
            "Run the relevant tests and return the evidence.",
        ],
        "deploy-checklist": [
            "Read `.agent/STATE.md`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.",
            "Check release readiness, documentation, and rollback expectations.",
            "Return a concise ship/no-ship checklist with blockers first.",
        ],
    }
    return "\n".join(commands[name])


def render_claude_command_from_workflow(name: str, workflow: dict) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(workflow["steps"], start=1))
    return f"""Use the generated workflow bundle `.agent/workflows/{name}.md`.

Goal: {workflow['goal']}
Skills: {', '.join(workflow['skills']) if workflow['skills'] else 'none'}

Steps:
{steps}
""" 


def managed_file_map(cwd: Path, profile: dict) -> dict[Path, str]:
    files: dict[Path, str] = {
        cwd / "AGENTS.md": render_agents_md(profile),
        cwd / ".agent" / "PROJECT.md": render_project_md(profile),
        cwd / ".agent" / "ROADMAP.md": render_roadmap_md(profile),
        cwd / ".agent" / "STATE.md": render_state_md(profile),
    }

    workflow_map = {}
    for workflow_name, workflow_goal in workflow_bundle_definitions(cwd):
        workflow = build_workflow(workflow_goal, cwd, max_skills=5)
        workflow_map[workflow_name] = workflow
        files[cwd / ".agent" / "workflows" / f"{workflow_name}.md"] = workflow_markdown(workflow_name, workflow)

    tools = selected_tools(profile)
    if "claude" in tools:
        files[cwd / "CLAUDE.md"] = render_claude_md(profile)
        for role in ["orchestrator", "researcher", "implementer", "reviewer"]:
            files[cwd / ".claude" / "agents" / f"{role}.md"] = render_claude_agent(role, profile)
        for command_name in ["brainstorm", "plan-feature", "implement-feature", "review-changes", "test-changes", "deploy-checklist"]:
            command_workflow = workflow_map.get(command_name) or build_workflow(command_name, cwd, max_skills=5)
            files[cwd / ".claude" / "commands" / f"{command_name}.md"] = render_claude_command_from_workflow(command_name, command_workflow)
    if "gemini" in tools:
        files[cwd / "GEMINI.md"] = render_gemini_md(profile)
    if "cursor" in tools:
        files[cwd / ".cursor" / "rules" / "skillsmith.mdc"] = render_cursor_rule(profile)
        files[cwd / ".cursorrules"] = render_legacy_cursor_rules(profile)
        for workflow_name, workflow in workflow_map.items():
            files[cwd / ".cursor" / "rules" / "workflows" / f"{workflow_name}.mdc"] = render_cursor_workflow_rule(workflow_name, workflow)
    if "windsurf" in tools:
        files[cwd / ".windsurf" / "rules" / "skillsmith.md"] = render_windsurf_rule(profile)
        files[cwd / ".windsurfrules"] = render_legacy_windsurf_rules(profile)
        for workflow_name, workflow in workflow_map.items():
            files[cwd / ".windsurf" / "workflows" / f"{workflow_name}.md"] = render_windsurf_workflow(workflow_name, workflow)
    if "zencoder" in tools:
        files[cwd / ".zencoder" / "rules" / "skillsmith.md"] = render_zencoder_rule(profile)
        for workflow_name, workflow in workflow_map.items():
            files[cwd / ".zencoder" / "rules" / "workflows" / f"{workflow_name}.md"] = render_zencoder_workflow_rule(workflow_name, workflow)
    if "copilot" in tools or "github-copilot" in tools:
        files[cwd / ".github" / "copilot-instructions.md"] = render_copilot_md(profile)

    return files


def managed_paths(cwd: Path) -> list[Path]:
    return [
        cwd / "AGENTS.md",
        cwd / ".agent" / "PROJECT.md",
        cwd / ".agent" / "ROADMAP.md",
        cwd / ".agent" / "STATE.md",
        cwd / ".agent" / "workflows" / "discover-project.md",
        cwd / ".agent" / "workflows" / "brainstorm.md",
        cwd / ".agent" / "workflows" / "plan-feature.md",
        cwd / ".agent" / "workflows" / "implement-feature.md",
        cwd / ".agent" / "workflows" / "debug-issue.md",
        cwd / ".agent" / "workflows" / "review-changes.md",
        cwd / ".agent" / "workflows" / "test-changes.md",
        cwd / ".agent" / "workflows" / "deploy-checklist.md",
        cwd / "CLAUDE.md",
        cwd / ".claude" / "agents" / "orchestrator.md",
        cwd / ".claude" / "agents" / "researcher.md",
        cwd / ".claude" / "agents" / "implementer.md",
        cwd / ".claude" / "agents" / "reviewer.md",
        cwd / ".claude" / "commands" / "brainstorm.md",
        cwd / ".claude" / "commands" / "plan-feature.md",
        cwd / ".claude" / "commands" / "implement-feature.md",
        cwd / ".claude" / "commands" / "review-changes.md",
        cwd / ".claude" / "commands" / "test-changes.md",
        cwd / ".claude" / "commands" / "deploy-checklist.md",
        cwd / "GEMINI.md",
        cwd / ".cursor" / "rules" / "skillsmith.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "discover-project.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "brainstorm.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "plan-feature.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "implement-feature.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "debug-issue.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "review-changes.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "test-changes.mdc",
        cwd / ".cursor" / "rules" / "workflows" / "deploy-checklist.mdc",
        cwd / ".cursorrules",
        cwd / ".windsurf" / "rules" / "skillsmith.md",
        cwd / ".windsurf" / "workflows" / "discover-project.md",
        cwd / ".windsurf" / "workflows" / "brainstorm.md",
        cwd / ".windsurf" / "workflows" / "plan-feature.md",
        cwd / ".windsurf" / "workflows" / "implement-feature.md",
        cwd / ".windsurf" / "workflows" / "debug-issue.md",
        cwd / ".windsurf" / "workflows" / "review-changes.md",
        cwd / ".windsurf" / "workflows" / "test-changes.md",
        cwd / ".windsurf" / "workflows" / "deploy-checklist.md",
        cwd / ".windsurfrules",
        cwd / ".zencoder" / "rules" / "skillsmith.md",
        cwd / ".zencoder" / "rules" / "workflows" / "discover-project.md",
        cwd / ".zencoder" / "rules" / "workflows" / "brainstorm.md",
        cwd / ".zencoder" / "rules" / "workflows" / "plan-feature.md",
        cwd / ".zencoder" / "rules" / "workflows" / "implement-feature.md",
        cwd / ".zencoder" / "rules" / "workflows" / "debug-issue.md",
        cwd / ".zencoder" / "rules" / "workflows" / "review-changes.md",
        cwd / ".zencoder" / "rules" / "workflows" / "test-changes.md",
        cwd / ".zencoder" / "rules" / "workflows" / "deploy-checklist.md",
        cwd / ".github" / "copilot-instructions.md",
    ]


def prune_unmanaged_files(cwd: Path, expected_paths: set[Path]) -> None:
    for path in managed_paths(cwd):
        if path in expected_paths:
            continue
        if path.exists():
            path.unlink()


def render_all(cwd: Path, profile: dict) -> None:
    files = managed_file_map(cwd, profile)
    for path, content in files.items():
        write_file(path, content)
    prune_unmanaged_files(cwd, set(files.keys()))
