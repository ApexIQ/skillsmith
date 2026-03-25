---
description: Design a parallelized execution graph for multiple agents.
---

# [/swarm] Swarm Orchestration Plan

## 1. Goal Analysis
- [ ] Decompose the high-level goal into atomic sub-tasks.
- [ ] Identify points for parallelization vs. sequential dependencies.

## 2. Agent Assignments
- [ ] [Orchestrator]: Overall sequence and state management.
- [ ] [Researcher]: Constraint gathering and context mapping.
- [ ] [Implementer]: Writing atomic, testable code increments.
- [ ] [Reviewer]: Advesarial check for quality and regressions.

## 3. Communication Protocol
- [ ] Define the output formats for each role handoff.
- [ ] Synchronize on the `.agent/STATE.md` update frequency.

// turbo
1. run_command { "CommandLine": "skillsmith swarm plan --goal \"<INSERT_GOAL>\"" }
