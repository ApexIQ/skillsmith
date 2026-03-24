# CLAUDE.md

## Prime Directives

1. Read `AGENTS.md` and `.agent/STATE.md` first.
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

## Testing Protocol

1. Set local environment: `$env:PYTHONPATH = "src"`.
2. Run unit tests: `uv run python -m unittest discover tests -v`.
3. Validate scaffolding: `uv run python -m skillsmith init --template <type> C:\Users\vanam\Desktop\lab`.
4. Run `skillsmith doctor C:\Users\vanam\Desktop\lab` (must pass 100/100).

## Completion Bar

- Keep work aligned with `.agent/PROJECT.md` and `.agent/ROADMAP.md`.
- Do not claim completion without concrete verification evidence.
- Prefer the simplest correct solution over clever complexity.


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
