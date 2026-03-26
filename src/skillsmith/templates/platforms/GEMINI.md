# GEMINI.md

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
- **Mandatory Mission Audit**: After complex executions, run `skillsmith audit` to verify trace integrity.
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

## Agent Commands

The following 33+ commands are available as structured workflows:
`brainstorm`, `plan-feature`, `implement-feature`, `review-changes`, `test-changes`, `deploy-checklist`, `debug-issue`, `refactor`, `debug`, `test`, `doc`, `audit`, `lint`, `compose`, `evolve`, `align`, `profile`, `report`, `sync`, `autonomous`, `context`, `verify`, `review`, `bootstrap`, `migrate`, `benchmark`, `security`, `performance`, `cleanup`, `search`, `explain`, `ready`, `tree`, **swarm**, **team-exec**.

## Quick References
- `.agent/PROJECT.md` for architecture and direction.
- `.agent/ROADMAP.md` for milestone priorities.
- `.agent/workflows/` for reusable runbooks.

## Skill Prototypes (Universal Logic)

> Engineering patterns and architecture prototypes are located in [.agent/context/prototypes.md]([.agent/context/prototypes.md]).
> Search there before implementing new files to ensure alignment with existing structures.
