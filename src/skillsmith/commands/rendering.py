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


def _resolve_prototypes(embodiment: str) -> str:
    """Resolve universal Skill Prototypes to specific agent embodiments (arXiv:2307.09955)."""
    prototype_dir = Path(__file__).parent.parent / "templates" / ".prototypes"
    if not prototype_dir.exists():
        return ""

    instructions = []
    for proto_file in prototype_dir.glob("*.yaml"):
        try:
            proto = yaml.safe_load(proto_file.read_text(encoding="utf-8"))
            if not proto:
                continue
            
            # Universal Logic
            instructions.append(f"### Prototype: {proto.get('name', proto_file.stem).title()}")
            instructions.append(proto.get("description", ""))
            
            logic = proto.get("logic", {})
            if isinstance(logic, dict):
                for section, steps in logic.items():
                    instructions.append(f"#### {section.replace('_', ' ').title()}")
                    if isinstance(steps, list):
                        for step in steps:
                            instructions.append(f"- {step}")
            
            # Embodiment-specific mapping
            emb_logic = proto.get("embodiments", {}).get(embodiment, [])
            if emb_logic:
                instructions.append(f"#### {embodiment.title()} Optimization")
                for step in emb_logic:
                    instructions.append(f"- {step}")
            
            instructions.append("")
        except Exception:
            continue
    
    if not instructions:
        return ""
    
    return "\n## Skill Prototypes (Universal Logic)\n\n" + "\n".join(instructions)


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

## 1. Prime Directives

1. Read `AGENTS.md` and `.agent/STATE.md` first.
2. Read `.agent/lessons.md` for long-term project memory and past mistakes.
3. Read `.agent/principles/CORE_PRINCIPLES.md` for project behavioral rules.
4. Read `.agent/project_profile.yaml` and `.agent/context/project-context.md` before making stack assumptions.
5. Search `.agent/skills/` for the most relevant instructions before implementation.
6. Follow the **7-Stage Workflow**: Discover → Plan → Build → Review → Test → Ship → Reflect.
7. **AND/OR Thinking**: Treat every goal as a root node in a dynamic Thinking Tree. If Strategy A fails, prune it and branch to Strategy B (OR) at the exact failure node.
8. Update `.agent/STATE.md` after significant steps.

## 2. The 7-Stage Development Cycle

| Stage | Objective |
|:---|:---|
| **Discover** | Audit profile, context, and code for constraints. |
| **Plan** | Define minimal patch with verification points. |
| **Build** | Implement atomic changes in isolation. |
| **Review** | Adversarial check for risks and regressions. |
| **Test** | Identify highest-risk behavior and verify. |
| **Ship** | Generate clean handoff with evidence. |
| **Reflect** | Record lessons and update project state. |

## 3. Execution Standard

- Plan first for non-trivial work (3+ steps, architecture changes, migrations, or risky edits).
- Keep fixes minimal and focused. Avoid broad refactors unless required for correctness.
- Delegate to subagents only for parallelizable or clearly specialized tasks.
- One owner per subtask; merge results only after verification.
- Never mark done without evidence (tests, command output, or concrete behavioral checks).

## Memory and Cost Policy (Library-First)

- Optimize for `pip install skillsmith` local workflows first; external services remain optional.
- Prefer retrieval reuse and cheap context operations before model-heavy loops.
- **Mandatory Memory Protocol**:
  - Read `.agent/lessons.md` (Layer 2) for long-term project memory and past mistakes.
  - Log tactical events to `.agent/logs/raw_events.jsonl` (Layer 1) for historical context.
- **Autonomous Evolution**:
  - Run `skillsmith evolve reflect` after multi-step missions to distill logs into lessons.
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

- .agent/context/project-context.md: generated repo context
- .agent/skills/`: reusable procedural skills
- .agent/workflows/`: internal workflow source layer

## Testing & Validation

### 1. Library Validation (CLI & Core)
To verify the core library logic:
```powershell
$env:PYTHONPATH = "src"
uv run python -m unittest discover tests -v
```

### 2. Scaffold Validation (The "Lab" Method)
To test project initialization in a clean environment:
```powershell
# Initialize from a template on the Desktop
uv run python -m skillsmith init --template fastapi-pro C:\\Users\\vanam\\Desktop\\test_lab

# Align and Doctor the lab
uv run python -m skillsmith align C:\\Users\\vanam\\Desktop\\test_lab
uv run python -m skillsmith doctor C:\\Users\\vanam\\Desktop\\test_lab
```

### 3. Acceptance Criteria
- `skillsmith doctor` returns **100/100**.
## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md](.agent/context/prototypes.md).
> Search there before implementing new files to ensure alignment with existing structures.
"""


def render_prototypes_md(profile: dict) -> str:
    """Render all Skill Prototypes into a single context file."""
    return f"""# Skill Prototypes

> Universal logic and patterns for autonomous engineering.
> These prototypes define the standard implementation patterns for this project.

{_resolve_prototypes('universal')}

---
*Generated by skillsmith align.*
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


def render_principles_md(profile: dict) -> str:
    priorities = profile.get("priorities", []) or ["maintainability", "verification"]
    return f"""# Core Principles

> **Standard Operating Procedure**: These rules are immutable and must be applied to every tool execution.

## 1. Engineering Priorities
""" + "\n".join(f"- **{p.title()}**: {p}" for p in priorities) + f"""

## 2. Security & Trust Policy
- **Remote Skills**: {"Allowed" if profile.get("allow_remote_skills") else "Blocked"}
- **GitHub Pins**: {"Required" if profile.get("require_pinned_github_refs", True) else "Optional"}
- **Trust Score**: {profile.get("min_remote_trust_score", 65)}+ required
- **Verification Mode**: {profile.get("publisher_verification_mode", "optional").upper()}

## 3. Behavioral Guardrails
- **Atomic Edits**: Never combine unrelated changes in a single file write.
- **Verification First**: Prove success with command output before claiming completion.
- **Minimalist Design**: Prefer the simplest code that satisfies the requirement.
- **No Placeholders**: Never use `// TODO` or `// implement later` in production-bound code.
"""

def render_claude_md(profile: dict) -> str:
    return f"""# CLAUDE.md

## Prime Directives

1. Read `AGENTS.md`, `.agent/STATE.md`, and `.agent/lessons.md` first.
2. Read `.agent/principles/CORE_PRINCIPLES.md` for project behavioral rules.
3. Read `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.
4. Search `.agent/skills/` before implementation.
5. Follow the **7-Stage Workflow**: Discover → Plan → Build → Review → Test → Ship → Reflect.

## 7-Stage Workflow

1. **Discover**: Audit profile, context, and code for constraints.
2. **Plan**: Define minimal patch with AND/OR branches (Recursion Strategy).
3. **Build**: Implement atomic changes in isolation.
4. **Review**: Adversarial check for risks and regressions.
5. **Test**: Identify highest-risk behavior and verify.
6. **Ship**: Generate clean handoff with evidence.
7. **Reflect**: Record lessons and update project state.

## Strategic Branching (Brain-Aware Tooling)

- **Failure pivots**: For complex tasks, if one approach (e.g., standard lib) fails, the orchestrator MUST pivot to an alternative (e.g., custom implementation) as a sibling branch.
- **Atomic Integrity**: Every `OR` strategy must be bound by its own `AND` verification subgoals.

## Slash Commands

Skillsmith provides 33+ specialized commands for high-fidelity engineering. Run these to maintain 100% architectural integrity:
- **Core Ops**: `/plan`, `/audit`, `/refactor`, `/ready`, `/sync`, `/profile`, `/report`, `/align`.
- **Specialists**: `/security`, `/performance`, `/benchmark`, `/migrate`, `/bootstrap`.
- **Engineering**: `/debug`, `/test`, `/doc`, `/lint`, `/verify`, `/review`.
- **Agent Orchestration**: [bold green]`/swarm`[/bold green], [bold green]`/team-exec`[/bold green], `/compose`, `/evolve`, `/autonomous`.
- **Knowledge**: `/context`, `/search`, `/explain`, `/brainstorm`.
- **Workflow**: `/plan-feature`, `/implement-feature`, `/review-changes`, `/test-changes`, `/debug-issue`, `/deploy-checklist`.

## Delegation Policy

- Use `.claude/agents/` when specialization or parallel execution materially helps.
- Do not delegate urgent blocking work that can be completed directly.
- Keep one clear subtask per subagent and avoid overlapping write scope.

## Memory and Cost Policy

- Use the library-first default: `skillsmith` is the portable brain.
- **Mandatory Memory Protocol**:
  - Read `.agent/lessons.md` (Layer 2) for long-term project memory and past mistakes.
  - Log tactical events to `.agent/logs/raw_events.jsonl` (Layer 1) for historical context.
- **Autonomous Evolution**:
  - Run `skillsmith evolve reflect` after multi-step missions to distill logs into lessons.
- Follow five layers: observer, reflector, recovery, watcher, safeguard.
- Require cache TTL and fingerprint invalidation for context reuse.

## Role Use

- `orchestrator`: set plan, assign role ownership, and gate completion.
- `researcher`: gather constraints and evidence before implementation starts.
- `implementer`: make focused edits and provide verification artifacts.
- `reviewer`: produce findings-first validation and regression checks.

## Role Handoff

- Include goal, scope, file list, verification run, and unresolved risks in each handoff.
- Prefer `researcher -> implementer -> reviewer -> orchestrator` for non-trivial tasks.

## Testing Protocol

1. Set local environment: `$env:PYTHONPATH = "src"`.
2. Run unit tests: `uv run python -m unittest discover tests -v`.
3. Validate scaffolding: `uv run python -m skillsmith init --template <type> C:\\Users\\vanam\\Desktop\\lab`.
4. Run `skillsmith doctor C:\\Users\\vanam\\Desktop\\lab` (must pass 100/100).

## Completion Bar

- Keep work aligned with `.agent/PROJECT.md` and `.agent/ROADMAP.md`.
- Do not claim completion without concrete verification evidence.
## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md](.agent/context/prototypes.md).
> Search there before implementing new files to ensure alignment with existing structures.
"""


def render_gemini_md(profile: dict) -> str:
    return f"""# GEMINI.md

## Prime Directives
1. Read `AGENTS.md`, `.agent/STATE.md`, and `.agent/lessons.md` first.
2. Read `.agent/principles/CORE_PRINCIPLES.md` for project behavioral rules.
3. Read `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.
4. Search `.agent/skills/` before implementation.
5. Follow the **7-Stage Workflow**: Discover → Plan → Build → Review → Test → Ship → Reflect.

## 7-Stage Workflow

1. **Discover**: Audit profile, context, and code for constraints.
2. **Plan**: Define minimal patch with verification points.
3. **Build**: Implement atomic changes in isolation.
4. **Review**: Adversarial check for risks and regressions.
5. **Test**: Identify highest-risk behavior and verify.
6. **Ship**: Generate clean handoff with evidence.
7. **Reflect**: Record lessons and update project state.

## Execution Policy
- Plan before coding for non-trivial work (3+ steps or architectural impact).
- Keep changes minimal, explicit, and easy to verify.
- Use subagents only when parallelism or specialization is clearly beneficial.
- Verify with tests/checks before marking done.

## Memory and Cost Policy
- Library-First: `skillsmith` is the source of truth for memory.
- **Mandatory Memory Protocol**:
  - Read `.agent/lessons.md` (Layer 2) for long-term project memory and past mistakes.
  - Log tactical events to `.agent/logs/raw_events.jsonl` (Layer 1).
- **Autonomous Evolution**:
  - Run `skillsmith evolve reflect` after multi-step missions to distill logs into lessons.
- Use the five-layer pattern: observer, reflector, recovery, watcher, safeguard.
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

## Agent Commands

The following 33+ commands are available as structured workflows:
`brainstorm`, `plan-feature`, `implement-feature`, `review-changes`, `test-changes`, `deploy-checklist`, `debug-issue`, `refactor`, `debug`, `test`, `doc`, `audit`, `lint`, `compose`, `evolve`, `align`, `profile`, `report`, `sync`, `autonomous`, `context`, `verify`, `review`, `bootstrap`, `migrate`, `benchmark`, `security`, `performance`, `cleanup`, `search`, `explain`, `ready`, `tree`, [bold green]`swarm`[/bold green], [bold green]`team-exec`[/bold green].

## Testing & Validation

1. Set environment: `$env:PYTHONPATH = "src"`.
2. Run tests: `uv run python -m unittest discover tests -v`.
3. Scaffold check: `uv run python -m skillsmith init --template fastapi-pro C:\\Users\\vanam\\Desktop\\lab_gemini`.
4. Health check: `uv run python -m skillsmith doctor C:\\Users\\vanam\\Desktop\\lab_gemini`.

## Quick References
- `.agent/PROJECT.md` for architecture and direction.
- `.agent/ROADMAP.md` for milestone priorities.
- `.agent/workflows/` for reusable runbooks.

## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md](.agent/context/prototypes.md).
> Search there before implementing new files to ensure alignment with existing structures.
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
- `.agent/lessons.md`
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

- Read `AGENTS.md`, `.agent/STATE.md`, and `.agent/lessons.md`.
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

- Read `AGENTS.md`, `.agent/STATE.md`, `.agent/lessons.md`, and `.agent/project_profile.yaml`.
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


def render_claude_command_from_workflow(name: str, workflow: dict, cwd: Path) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(workflow["steps"], start=1))
    return f"""# Command: /{name}

> This command is powered by a dynamic Skillsmith workflow bundle.

## Goal
{workflow['goal']}

## Resources
- **Workflow Bundle**: [.agent/workflows/{name}.md](file:///{cwd.as_posix()}/.agent/workflows/{name}.md)
- **Top Skills**: {', '.join(workflow['skills']) if workflow['skills'] else 'none selected'}

## Execution Plan
{steps}

---
*Generated by skillsmith align.*
""" 


def managed_file_map(cwd: Path, profile: dict) -> dict[Path, str]:
    files: dict[Path, str] = {
        cwd / "AGENTS.md": render_agents_md(profile),
        cwd / ".agent" / "PROJECT.md": render_project_md(profile),
        cwd / ".agent" / "ROADMAP.md": render_roadmap_md(profile),
        cwd / ".agent" / "STATE.md": render_state_md(profile),
        cwd / ".agent" / "principles" / "CORE_PRINCIPLES.md": render_principles_md(profile),
        cwd / ".agent" / "context" / "prototypes.md": render_prototypes_md(profile),
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
        for command_name in ["brainstorm", "plan-feature", "implement-feature", "review-changes", "test-changes", "deploy-checklist", "debug-issue",
                             "refactor", "debug", "test", "doc", "audit", "lint", "compose", "evolve", "align", "profile", "report", 
                             "sync", "autonomous", "context", "verify", "review", "bootstrap", "migrate", "benchmark", "security", 
                             "performance", "cleanup", "search", "explain", "ready", "swarm", "team-exec"]:
            command_workflow = workflow_map.get(command_name) or build_workflow(command_name, cwd, max_skills=5)
            files[cwd / ".claude" / "commands" / f"{command_name}.md"] = render_claude_command_from_workflow(command_name, command_workflow, cwd)
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
    paths = [
        cwd / "AGENTS.md",
        cwd / ".agent" / "PROJECT.md",
        cwd / ".agent" / "ROADMAP.md",
        cwd / ".agent" / "STATE.md",
        cwd / ".agent" / "principles" / "CORE_PRINCIPLES.md",
        cwd / "CLAUDE.md",
        cwd / "GEMINI.md",
        cwd / ".cursor" / "rules" / "skillsmith.mdc",
        cwd / ".cursorrules",
        cwd / ".windsurf" / "rules" / "skillsmith.md",
        cwd / ".windsurfrules",
        cwd / ".zencoder" / "rules" / "skillsmith.md",
        cwd / ".github" / "copilot-instructions.md",
        cwd / ".agent" / "context" / "prototypes.md",
    ]
    
    for role in ["orchestrator", "researcher", "implementer", "reviewer"]:
        paths.append(cwd / ".claude" / "agents" / f"{role}.md")

    workflow_names = [
        "discover-project", "brainstorm", "plan-feature", "implement-feature", "debug-issue", 
        "review-changes", "test-changes", "deploy-checklist", "refactor", "debug", "test", 
        "doc", "audit", "lint", "compose", "evolve", "align", "profile", "report", "sync", 
        "autonomous", "context", "verify", "review", "bootstrap", "migrate", "benchmark", 
        "security", "performance", "cleanup", "search", "explain", "ready", "swarm", "team-exec"
    ]
    
    for name in workflow_names:
        paths.append(cwd / ".agent" / "workflows" / f"{name}.md")
        paths.append(cwd / ".claude" / "commands" / f"{name}.md")
        paths.append(cwd / ".cursor" / "rules" / "workflows" / f"{name}.mdc")
        paths.append(cwd / ".windsurf" / "workflows" / f"{name}.md")
        paths.append(cwd / ".zencoder" / "rules" / "workflows" / f"{name}.md")

    return paths


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
