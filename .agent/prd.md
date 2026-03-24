# [.agent/prd.md] / Self-Evolution Engine (Phase 2)

## 1. Overview
The **Self-Evolution Engine** is the intelligence layer that transforms static Skillsmith skills into living, learning assets. By capturing execution telemetry and analyzing successful/failed agent workflows, Skillsmith can auto-repair degraded skills, derive specialized variants for specific frameworks, and capture entirely new skills from novel successful executions. This removes the manual maintenance burden of prompt engineering and ensures our AI agents never make the same mistake twice.

## 2. Business & User Context
- **Market Positioning**: Competitors (ECC, Cursor) use static instruction sets. Skillsmith will be the first tool to offer **"Skills with a Memory"**.
- **User Needs**: Professional AI engineers need to trust that their instructions are improving over time, not drifting into irrelevance.
- **Goal**: 100% automated skill improvement with human-in-the-loop trust verification.

## 3. Functional Requirements
### F1: Skill Telemetry (Metric Capture)
- Capture `applied_count`, `success_rate`, `fallback_rate`, `token_cost`, and `execution_time`.
- Persist telemetry in `skills.lock.json` with per-version granularity.
### F2: Execution Analysis Hook
- Add `--learn` to `skillsmith compose`.
- Analyze execution traces (terminal outputs, file diffs, linter results).
- Map outcomes back to the skills used.
### F3: `skillsmith evolve` (Core Logic)
- **FIX Mode**: Auto-patch SKILL.md based on frequency-of-failure patterns.
- **DERIVE Mode**: Clone parent skills and specialize for specific contexts (e.g. `python-expert` -> `fastapi-expert`).
- **CAPTURE Mode**: Create a brand new SKILL.md from a successful execution that used no pre-defined skill.
### F4: Version DAG (Lineage)
- Every evolution creates a new version entry in `.agent/skills/<name>/versions/`.
- Maintain a `lineage.json` tracking the parent-child relationship and improvement metrics.

## 4. Non-Functional Requirements (NFR)
- **Performance**: Analysis hooks must add <200ms of overhead to non-LLM operations.
- **Privacy**: No PII or proprietary code snippets stored in telemetry without explicit `--learn` opt-in.
- **Scalability**: Support projects with 100+ skills and 1000s of execution traces.
- **Determinism**: Evolutions should be reproducible given the same trace data.

## 5. UX & Interaction Specs
- **Command**: `skillsmith metrics` -> Dashboard view of skill health.
- **Command**: `skillsmith evolve --interactive` -> Step-through evolution logic for human approval.
- **Feedback**: After a successful task, the CLI suggests: *"Novel pattern detected! Run 'skillsmith evolve --mode capture' to create a new skill."*

## 6. AI / Model Expectations
- Use LLMs (Claude-3.5-Sonnet/Gemini-2.0) for the `evolve` analysis pass.
- **Evaluation Rubric**: Evolved skills must demonstrate a >10% improvement in `success_rate` across 5 test-harness runs before being promoted to `active`.

## 7. Risks & Mitigations
- **Over-Evolution**: Skills might become too specialized or "overfit" to one session. *Mitigation: Cap evolution frequency (max 3 per day).*
- **Hallucinated Fixes**: Evolutionary patches might introduce incorrect syntax. *Mitigation: Mandatory `skillsmith lint` pass after every evolution.*
- **Context Rot**: Telemetry might become stale. *Mitigation: TTL-based metric weighting (newer runs weigh more).*

## 8. Success Metrics & KPIs
- **Quantitative**: 20% reduction in `fallback_rate` for core skills across 100 sessions.
- **Qualitative**: High user confidence in `evolve` suggestions (measured by approval rate).
- **Metric**: Token cost-per-successful-task reduced by 15% through better skill precision.

## 9. Dependencies
- SQLite durable datastore (for local metric persistence).
- Execution trace capture logic in `compose` and `autonomous`.
- `skillsmith.lock.json` schema v3.

## 10. Revision History
- **2026-03-25**: Initial Draft (Phase 2 Roadmap) by Antigravity.
