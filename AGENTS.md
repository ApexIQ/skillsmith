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

- `.agent/skills/`: reusable task guides.
- `.agent/params/`: project constraints.

## Project Structure

- `.agent/skills/`: reusable task guides.
- `.agent/params/`: project constraints.
- `.agent/PROJECT.md`: product and architecture context.
- `.agent/ROADMAP.md`: strategic milestones.
- `.agent/STATE.md`: current tactical state.
- `.agent/project_profile.yaml`: structured project source of truth.
- `.agent/context/project-context.md`: generated repository context.

## Testing & Validation

### 1. Library Validation (CLI & Core)
To verify the core library logic and CLI commands:
```powershell
# Set PYTHONPATH to the src directory
$env:PYTHONPATH = "src"

# Run the test suite
uv run python -m unittest discover tests -v
```

### 2. Scaffold Validation (The "Lab" Method)
To test project initialization and alignment in a clean environment:
```powershell
# 1. Create a temporary lab directory
mkdir test_lab

# 2. Initialize from a template
uv run python -m skillsmith init --template fastapi-pro test_lab

# 3. Align the project (updates agents, rules, and workflows)
uv run python -m skillsmith align test_lab

# 4. Run the doctor to verify 100% healthy alignment
uv run python -m skillsmith doctor test_lab
```

### 3. Acceptance Criteria
- `skillsmith doctor` must return **100/100** with no failing checks.
- All tool-native instruction files (CLAUDE.md, GEMINI.md, etc.) must be rendered.
- All 33+ managed slash commands must be present in `.claude/commands/`.
- All workflow bundles must be present in `.agent/workflows/`.

## Active Skills

Run `skillsmith list` to see available skills in `.agent/skills/`.
