# CLAUDE.md

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
3. Validate scaffolding: `uv run python -m skillsmith init --template <type> C:\Users\vanam\Desktop\lab`.
4. Run `skillsmith doctor C:\Users\vanam\Desktop\lab` (must pass 100/100).

## Completion Bar

- Keep work aligned with `.agent/PROJECT.md` and `.agent/ROADMAP.md`.
- Do not claim completion without concrete verification evidence.
## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md](.agent/context/prototypes.md).
> Search there before implementing new files to ensure alignment with existing structures.
