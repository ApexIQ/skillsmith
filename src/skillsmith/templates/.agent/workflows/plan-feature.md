---
description: Plan a new feature implementation with technical rigor and acceptance criteria.
---

# [/plan-feature] Implementation Plan

## 1. Problem Context & Objectives
- Summary of the request.
- Key technical constraints (stack, existing patterns).
- Explicit non-goals.

## 2. Proposed Changes
- [ ] **Data Layer**: Schema updates, migrations.
- [ ] **Core Logic**: New modules, algorithm changes.
- [ ] **API/Interface**: Endpoint updates, function signatures.
- [ ] **UX/UI**: Styling, interaction states.

## 3. Verification & Acceptance Criteria
- [ ] **Lints**: Run `uv run ruff check` or equivalent.
- [ ] **Tests**: Specific test cases to pass.
- [ ] **Manual Check**: Concrete behavioral evidence.

## 4. Risks & Falling Back
- What could break existing logic?
- Rollback strategy.

// turbo
1. run_command { "CommandLine": "ls -R .agent/skills" }
2. run_command { "CommandLine": "grep -rn 'TODO' src/" }
