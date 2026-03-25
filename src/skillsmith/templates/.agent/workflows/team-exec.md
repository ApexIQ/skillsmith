---
description: Execute a coordinated multi-agent mission with verifiable handoffs.
---

# [/team-exec] Mission Execution Harness

## 1. Kickoff (Orchestrator)
- [ ] Initialize the `.agent/MISSION.md` with goals.
- [ ] Confirm dependencies are ready.

## 2. Context Recon (Researcher)
- [ ] Audit relevant modules and patterns.
- [ ] Document constraints in `.agent/RESEARCH.md`.

## 3. Implementation (Implementer)
- [ ] Apply changes with 100% adherence to Research findings.
- [ ] Document implementation details in `.agent/status.md`.

## 4. Verification (Reviewer)
- [ ] Adversarial testing and code review.
- [ ] Final verification against acceptance criteria.

// turbo
1. run_command { "CommandLine": "skillsmith team-exec \"<INSERT_GOAL>\"" }
