# [.agent/prd.md] / Mission Control Protocol (Swarm Orchestration)

## 1. Overview
Current `swarm` logic is a high-fidelity simulation but lacks deterministic state management and real agent handoff mechanisms. The **Mission Control Protocol (MCP)** provides the stateful layer required for specialized AI personas (Researcher, Implementer, Reviewer) to coordinate asynchronously through a shared `.agent/mission.json` contract.

## 2. Business & User Context
- **User Nees**: Developers need multi-agent coordination that isn't just "toy logic" but acts as a production-grade GSD (Get Stuff Done) engine.
- **Differentiation**: Unlike LiteLLM/Agno which focus on the LLM call, Skillsmith focuses on the **Execution State** and **Trust Verification** between roles.

## 3. Functional Requirements
- [x] **Stateful Schema**: Implement `.agent/mission.json` to track lifecycle (Pending, In Progress, Blocked, Completed, Verified). [DONE]
- [x] **Handoff Packets**: Generate role-specific context packets (Goal + Context + Persona-Skill + Constraints). [DONE]
- [x] **Reactive Sync**: Keep `.agent/MISSION.md` in sync with the JSON state for human observability. [DONE]
- [x] **Phase 3.5: Eval-to-Evolve Bridge**: `eval --auto-evolve` triggers skill repair via `EvolutionEngine`. [DONE]
- [ ] **Thinking Tree Integration**: Map mission steps directly to `workflow.json` OR/AND nodes. [PLAN]
- [ ] **Verification Gates**: Prevent task completion until a `Reviewer` or `L4 Watcher` verifies the fingerprint/trust. [PLAN]

## 4. Non-Functional Requirements (NFR)
- **Performance**: State transitions must be sub-50ms (local file ops).
- **Scalability**: Support up to 50 concurrent task nodes in a Thinking Tree.
- **Reliability**: No manual parsing of Markdown for state; JSON is the source of truth.

## 5. UX & Interaction Specs
- `skillsmith swarm plan "Goal"` -> Creates JSON + MD + Tree.
- `skillsmith swarm status` -> Visualizes progress via Rich tables.
- `skillsmith swarm execute` -> The deterministic loop that emits handoffs.

## 6. AI / Model Expectations
- The agent (Implementer/Researcher) must receive a high-fidelity context packet that includes the **Assigned Persona Skill**.
- Evaluation rubric: 100% of tasks must map to a verifiable artifact.

## 7. Risks & Mitigations
- **State Drift**: JSON and MD getting out of sync. *Mitigation: Unidirectional sync (JSON -> MD).*
- **Blocked Reasoning**: Agent gets stuck in a loop. *Mitigation: TTL and "Strategic OR" branch fallbacks.*

## 8. Success Metrics & KPIs
- 100% Deterministic state tracking.
- Zero-logic simulation replaced by Handoff Protocol.

## 9. Dependencies
- `workflow_engine.py` (Thinking Tree DNA).
- `hashing.py` (Artifact integrity).

## 10. Revision History
- 2026-03-25: Initial PRD for Mission Control Protocol.
