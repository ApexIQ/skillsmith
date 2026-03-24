---
version: 0.1.0
name: how-to-create-implementation-plan
description: Use this skill when creating technical design documents (RFCs) before implementing features.
---

# 📝 How to Create an Implementation Plan

> **Why:** A plan is a contract. It prevents "scope creep" and ensures alignment before coding.

## 1. Structure (The Blueprint)
Every implementation plan should include:

### A. Goal & Overview
*   **Goal:** 1-sentence summary (e.g., "Add user authentication").
*   **Background:** Why is this needed? What problem does it solve?
*   **User Review:** Flag breaking changes or significant tech decisions.

### B. Proposed Changes
Group by component (Frontend/Backend/Database).
*   **[NEW]** File/component to create.
*   **[MODIFY]** Existing file + bullet points of changes.
*   **[DELETE]** Files to remove.

### C. Verification Plan
*   **Automated Tests:** What tests will cover this?
*   **Manual Testing:** Step-by-step "click path" to verify the feature.

### D. Risks & Considerations
*   What could go wrong?
*   Are there alternative approaches?

## 2. Methodology
1.  **Research First:** Understand the existing code before proposing changes.
2.  **Think in Systems:** If you add a frontend button, does the backend API exist?
3.  **Keep it Bite-Sized:** Plans >3 days of work should be split into phases.

## 3. Checklist
- [ ] Is the goal clearly stated?
- [ ] Are all affected files listed?
- [ ] Is the verification plan executable?
- [ ] Have risks been considered?

## Examples
*   **Good plan:** Clear goal, specific file changes, test plan included.
*   **Bad plan:** Vague "refactor backend", no specifics.

## Guidelines
*   Get plan approved before writing code.
*   Update the plan if scope changes during implementation.
