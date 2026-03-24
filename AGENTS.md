# AGENTS.md

> Primary project instructions for AI coding agents.

## 1. Prime Directives

1. Read `AGENTS.md` and `.agent/STATE.md` first.
2. Read `.agent/principles/CORE_PRINCIPLES.md` for project behavioral rules.
3. Read `.agent/project_profile.yaml` and `.agent/context/project-context.md` before making stack assumptions.
4. Search `.agent/skills/` for the most relevant instructions before implementation.
5. Follow the **7-Stage Workflow**: Discover → Plan → Build → Review → Test → Ship → Reflect.
6. **AND/OR Thinking**: Treat every goal as a root node in a dynamic Thinking Tree. If Strategy A fails, prune it and branch to Strategy B (OR) at the exact failure node.
7. Update `.agent/STATE.md` after significant steps.

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
- All 33+ slash commands rendered in `.claude/commands/`: `brainstorm`, `plan-feature`, `implement-feature`, `review-changes`, `test-changes`, `deploy-checklist`, `debug-issue`, `refactor`, `debug`, `test`, `doc`, `audit`, `lint`, `compose`, `evolve`, `align`, `profile`, `report`, `sync`, `autonomous`, `context`, `verify`, `review`, `bootstrap`, `migrate`, `benchmark`, `security`, `performance`, `cleanup`, `search`, `explain`, `ready`, [bold green]`swarm`[/bold green], [bold green]`team-exec`[/bold green].


## Skill Prototypes (Universal Logic)

### Prototype: --Init--
Autonomously discovered prototype from __init__.py
#### Discovered Patterns
- Analyzed .py file with 274 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of __init__.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in __init__.py.

### Prototype: Add
Autonomously discovered prototype from add.py
#### Discovered Patterns
- Analyzed .py file with 375 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of add.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in add.py.

### Prototype: Autonomy-Runtime
Autonomously discovered prototype from autonomy_runtime.py
#### Discovered Patterns
- Analyzed .py file with 1502 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of autonomy_runtime.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in autonomy_runtime.py.

### Prototype: Context-Index
Autonomously discovered prototype from context_index.py
#### Discovered Patterns
- Analyzed .py file with 1749 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of context_index.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in context_index.py.

### Prototype: Evolve
Autonomously discovered prototype from evolve.py
#### Discovered Patterns
- Analyzed .py file with 173 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of evolve.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in evolve.py.

### Prototype: Init
Autonomously discovered prototype from init.py
#### Discovered Patterns
- Analyzed .py file with 740 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of init.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in init.py.

### Prototype: Providers
Autonomously discovered prototype from providers.py
#### Discovered Patterns
- Analyzed .py file with 1092 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of providers.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in providers.py.

### Prototype: Ready
Autonomously discovered prototype from ready.py
#### Discovered Patterns
- Analyzed .py file with 627 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of ready.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in ready.py.

### Prototype: Registry-Service
Autonomously discovered prototype from registry_service.py
#### Discovered Patterns
- Analyzed .py file with 1334 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of registry_service.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in registry_service.py.

### Prototype: Rendering
Autonomously discovered prototype from rendering.py
#### Discovered Patterns
- Analyzed .py file with 819 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of rendering.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in rendering.py.

### Prototype: Report
Autonomously discovered prototype from report.py
#### Discovered Patterns
- Analyzed .py file with 645 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of report.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in report.py.

### Prototype: Suggest
Autonomously discovered prototype from suggest.py
#### Discovered Patterns
- Analyzed .py file with 292 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of suggest.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in suggest.py.

### Prototype: Thinking-Tree
Universal logic for AND/OR Thinking Tree orchestration (arXiv:2603.05294v1).
#### And Nodes
- Bind every action to a strict validator.
- Stop immediately on state violation (AND-failure).
#### Or Nodes
- If a path fails, pivot to Strategy B at the exact failure point.
- Re-conceive the solution instead of linear retry.
#### State Lifecycle
- Entering: Evidence gathering and branch selection.
- Exiting: Verification and result propagation.
#### Claude Optimization
- Use markdown lists for AND/OR labels.
- Focus on XML-style tags for state transitions.

### Prototype: Trust-Service
Autonomously discovered prototype from trust_service.py
#### Discovered Patterns
- Analyzed .py file with 1550 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of trust_service.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in trust_service.py.

### Prototype: Workflow-Engine
Autonomously discovered prototype from workflow_engine.py
#### Discovered Patterns
- Analyzed .py file with 932 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of workflow_engine.py.
- Ensure separation of concerns as seen in the original source.
#### Claude Optimization
- Implement with strict type safety as observed in workflow_engine.py.
