# AGENTS.md

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
| **Ship** | Generate clean handoff; run `evolve reflect` to prepare context. |
| **Reflect** | Distill exported reflection context into `lessons.md`. |

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

- Idea: Project using skillsmith
- Stage: existing
- App type: library
- Languages: python
- Frameworks: click, pytest
- Package manager: uv
- Deployment target: github-actions
- Priorities: testability, maintainability, verification, automation
- Target tools: antigravity, claude, codex, copilot, cursor, gemini, windsurf
- Trusted skill sources: local
- Allowed remote domains: github.com, skills.sh
- Require pinned GitHub refs: true
- Trusted publisher keys: none
- Trusted publisher public keys: none
- Publisher verification mode: optional
- Publisher signature scheme mode: auto
- Allowed publisher signature algorithms: hmac-sha256, rsa-sha256
- Publisher key rotation: none
- Minimum remote trust: 65

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
uv run python -m skillsmith init --template fastapi-pro C:\Users\vanam\Desktop\test_lab

# Align and Doctor the lab
uv run python -m skillsmith align C:\Users\vanam\Desktop\test_lab
uv run python -m skillsmith doctor C:\Users\vanam\Desktop\test_lab
```

### 3. Acceptance Criteria
- `skillsmith doctor` returns **100/100**.
## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md](.agent/context/prototypes.md).
> Search there before implementing new files to ensure alignment with existing structures.
