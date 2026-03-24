# AGENTS.md - Context and Instructions for AI Agents

> Start here. This is the primary entry point for agents working in this project.

## 1. Prime Directives

1. Read `AGENTS.md` and `.agent/STATE.md` first.
2. Read `.agent/principles/CORE_PRINCIPLES.md` for project behavioral rules.
3. Read `.agent/project_profile.yaml` and `.agent/context/project-context.md`.
4. Search `.agent/skills/` and read the 2-3 most relevant `SKILL.md` files before planning.
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


## Execution Standard

- Plan first for non-trivial work (3+ steps, architecture changes, migrations, or risky edits).
- Keep fixes minimal and focused; avoid broad refactors unless required.
- Delegate to subagents only when specialization or parallel work clearly helps.
- Keep one owner per subtask and avoid overlapping write scope.
- Never mark done without evidence (tests, command output, or concrete behavior checks).

## Memory and Cost Policy (Library-First)

- Optimize for `pip install skillsmith` local workflows first; external services must stay optional.
- Prefer low-cost retrieval paths before expensive model loops.
- Apply the five-layer memory approach in this order:
  1. observer capture,
  2. reflector compaction,
  3. session recovery,
  4. reactive watcher refresh,
  5. pre-compaction safeguard.
- Use TTL + fingerprint invalidation for recall caches to prevent stale context reuse.
- Do not introduce mandatory infra (OIDC/KMS/hosted services) for core library success paths.

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

## Project Structure

- `.agent/skills/`: reusable procedural skills.
- `.agent/principles/`: project behavioral rules.
- `.agent/hooks/`: tool execution automations.
- `.agent/scripts/`: project helper utilities.
- `.agent/PROJECT.md`: product and architecture context.
- `.agent/ROADMAP.md`: strategic milestones.
- `.agent/STATE.md`: current tactical state.
- `.agent/project_profile.yaml`: structured project source of truth.
- `.agent/context/project-context.md`: generated repository context.

## Active Skills

Run `skillsmith list` to see available skills in `.agent/skills/`.
