---
description: Implement a feature based on an agreed plan with atomic commits and verification.
---

# [/implement-feature] Execution

## 1. Environment Verification
- [ ] Check if `.agent/project_profile.yaml` is aligned.
- [ ] Check for existing tests or blockers.

## 2. Implementation Loop (AND/OR Thinking)
- [x] Initial Codebase Audit.
- [ ] Atomic Change 1.
- [ ] Atomic Change 2.
- [ ] Verification of Change.

## 3. Post-Implementation Review
- [ ] Run `skillsmith doctor` if applicable.
- [ ] Run `skillsmith ready` before completion.

---
// turbo
1. run_command { "CommandLine": "git status" }
2. run_command { "CommandLine": "uv run pytest tests/" }
