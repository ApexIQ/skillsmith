# GEMINI.md

## Prime Directives
1. Read `AGENTS.md` and `.agent/STATE.md` first.
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
- Idea: Project using skillsmith
- Languages: python
- Frameworks: click, pytest
- Trusted publisher public keys: none
- Publisher signature scheme mode: auto

## Agent Commands

The following 33+ commands are available as structured workflows:
`brainstorm`, `plan-feature`, `implement-feature`, `review-changes`, `test-changes`, `deploy-checklist`, `debug-issue`, `refactor`, `debug`, `test`, `doc`, `audit`, `lint`, `compose`, `evolve`, `align`, `profile`, `report`, `sync`, `autonomous`, `context`, `verify`, `review`, `bootstrap`, `migrate`, `benchmark`, `security`, `performance`, `cleanup`, `search`, `explain`, `ready`, `tree`, [bold green]`swarm`[/bold green], [bold green]`team-exec`[/bold green].

## Testing & Validation

1. Set environment: `$env:PYTHONPATH = "src"`.
2. Run tests: `uv run python -m unittest discover tests -v`.
3. Scaffold check: `uv run python -m skillsmith init --template fastapi-pro C:\Users\vanam\Desktop\lab_gemini`.
4. Health check: `uv run python -m skillsmith doctor C:\Users\vanam\Desktop\lab_gemini`.

## Quick References
- `.agent/PROJECT.md` for architecture and direction.
- `.agent/ROADMAP.md` for milestone priorities.
- `.agent/workflows/` for reusable runbooks.


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
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in __init__.py.

### Prototype: Add
Autonomously discovered prototype from add.py
#### Discovered Patterns
- Analyzed .py file with 375 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of add.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in add.py.

### Prototype: Autonomy-Runtime
Autonomously discovered prototype from autonomy_runtime.py
#### Discovered Patterns
- Analyzed .py file with 1502 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of autonomy_runtime.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in autonomy_runtime.py.

### Prototype: Context-Index
Autonomously discovered prototype from context_index.py
#### Discovered Patterns
- Analyzed .py file with 1749 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of context_index.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in context_index.py.

### Prototype: Evolve
Autonomously discovered prototype from evolve.py
#### Discovered Patterns
- Analyzed .py file with 173 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of evolve.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in evolve.py.

### Prototype: Init
Autonomously discovered prototype from init.py
#### Discovered Patterns
- Analyzed .py file with 740 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of init.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in init.py.

### Prototype: Providers
Autonomously discovered prototype from providers.py
#### Discovered Patterns
- Analyzed .py file with 1092 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of providers.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in providers.py.

### Prototype: Ready
Autonomously discovered prototype from ready.py
#### Discovered Patterns
- Analyzed .py file with 627 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of ready.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in ready.py.

### Prototype: Registry-Service
Autonomously discovered prototype from registry_service.py
#### Discovered Patterns
- Analyzed .py file with 1334 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of registry_service.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in registry_service.py.

### Prototype: Rendering
Autonomously discovered prototype from rendering.py
#### Discovered Patterns
- Analyzed .py file with 819 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of rendering.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in rendering.py.

### Prototype: Report
Autonomously discovered prototype from report.py
#### Discovered Patterns
- Analyzed .py file with 645 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of report.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in report.py.

### Prototype: Suggest
Autonomously discovered prototype from suggest.py
#### Discovered Patterns
- Analyzed .py file with 292 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of suggest.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in suggest.py.

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
#### Gemini Optimization
- Prioritize bold headers for node types.
- Use bulleted lists for state propagation.

### Prototype: Trust-Service
Autonomously discovered prototype from trust_service.py
#### Discovered Patterns
- Analyzed .py file with 1550 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of trust_service.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in trust_service.py.

### Prototype: Workflow-Engine
Autonomously discovered prototype from workflow_engine.py
#### Discovered Patterns
- Analyzed .py file with 932 lines.
- Detected high-density logical structures (classes/interfaces).
- Self-evolving agents should prioritize this pattern for similar system designs.
#### Core Implementation Rules
- Match the structural integrity of workflow_engine.py.
- Ensure separation of concerns as seen in the original source.
#### Gemini Optimization
- Use descriptive documentation matching the patterns found in workflow_engine.py.
