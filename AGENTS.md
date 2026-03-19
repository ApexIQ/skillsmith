# AGENTS.md - Context and Instructions for AI Agents

> Start here. This is the primary entry point for agents working in this project.

## Prime Directives

1. Read `.agent/STATE.md` first.
2. Read `.agent/project_profile.yaml` and `.agent/context/project-context.md` before making assumptions.
3. Search `.agent/skills/` and read the 2-3 most relevant `SKILL.md` files before planning.
4. Follow the loop: Discuss -> Plan -> Execute -> Verify.
5. Update `.agent/STATE.md` after significant steps.

## Execution Standard

- Plan first for non-trivial work (3+ steps, architecture changes, migrations, or risky edits).
- Keep fixes minimal and focused; avoid broad refactors unless required.
- Delegate to subagents only when specialization or parallel work clearly helps.
- Keep one owner per subtask and avoid overlapping write scope.
- Never mark done without evidence (tests, command output, or concrete behavior checks).

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

- `.agent/skills/`: reusable task guides.
- `.agent/params/`: project constraints.
- `.agent/PROJECT.md`: product and architecture context.
- `.agent/ROADMAP.md`: strategic milestones.
- `.agent/STATE.md`: current tactical state.
- `.agent/project_profile.yaml`: structured project source of truth.
- `.agent/context/project-context.md`: generated repository context.

## Active Skills

Run `skillsmith list` to see available skills in `.agent/skills/`.
