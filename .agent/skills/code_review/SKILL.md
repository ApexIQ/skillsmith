---
version: 0.1.0
name: code-review
description: Use this skill when reviewing code (your own or others'). It provides a structured checklist to catch bugs and ensure quality.
---

# 👁️ Code Review

> **Philosophy:** Code review is not about finding blame. It's about finding bugs *before* users do.

## The Checklist

### 1. Correctness
- [ ] Does the code do what the PR description says?
- [ ] Are edge cases handled (empty lists, null values, network errors)?
- [ ] Are there any off-by-one errors in loops?

### 2. Security
- [ ] Is user input validated/sanitized?
- [ ] Are ownership checks in place for resources?
- [ ] Are secrets hardcoded? (They shouldn't be.)

### 3. Performance
- [ ] Any N+1 queries? (Fetching in a loop instead of batch)
- [ ] Are large lists paginated?
- [ ] Is there unnecessary re-rendering in React components?

### 4. Readability
- [ ] Are variable/function names descriptive?
- [ ] Is complex logic explained with comments?
- [ ] Is the code DRY (no copy-paste)?

### 5. Testing
- [ ] Are there tests for the new code?
- [ ] Do the tests cover the happy path AND error cases?

## Examples
*   **Good PR:** Small, focused, with tests and a clear description.
*   **Bad PR:** 500+ lines, touches unrelated files, no tests.

## Guidelines
*   Review in <30 mins. If PR is too large, ask to split it.
*   Be kind. "Consider using X" is better than "This is wrong."
*   If unsure, ask questions instead of blocking.
