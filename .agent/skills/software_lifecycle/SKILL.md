---
version: 0.1.0
name: software-lifecycle
description: Use this skill at the start of any new feature or bug fix. It defines
  the standard operating procedure for shipping code.
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# ♾️ Software Lifecycle Strategy

> **Rule:** We do not just "write code". We follow a rigorous engineering process to ensure quality and prevent regressions.

## The Cycle

### 1. 🔍 Discovery & Skill Search (Search-then-GSD)
*   **Rule:** Before planning, **SEARCH** `.agent/skills/` for the 2-3 most relevant skills.
*   **Action:**
    *   Read the relevant skills to understand the "How-to".
    *   Research existing code and patterns.
    *   Check competitors and industry standards.
*   **Deliverable:** Orient yourself and update the project's PRD if scope changes.

### 2. 📝 Technical Design (RFC)
*   **Rule:** **NEVER write code without a plan.**
*   **Action:** Create an implementation plan or RFC document.
*   **Review:** Get approval for changes >20 lines or architectural decisions.

### 3. ⚡ Execution (The "Flow")
*   **Action:** Write code in small, testable chunks.
*   **Rule:** Track progress through a task list or issue tracker.
*   **Rule:** Follow TDD when writing new logic (see skill: `test_driven_development`).

### 4. 🛡️ Verification
*   **Action:** Run automated tests (unit, integration, E2E).
*   **Action:** Manual verification for UI/UX changes.
*   **Deliverable:** Create a walkthrough or demo if significant.

### 5. 📦 Documentation
*   **Action:** Update project status/changelog.
*   **Action:** Document new patterns in project documentation.

## Examples
*   **Feature Request:** Discovery -> Plan (RFC) -> TDD (Red/Green) -> Commit -> Demo.
*   **Bug Fix:** Reproduce -> Write failing test -> Fix -> Commit.

## Guidelines
*   Break large tasks into smaller subtasks.
*   If unsure, ask for clarification *before* building, not after.
*   Never skip the plan for changes >20 lines.
