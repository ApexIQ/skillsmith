---
version: 0.1.0
name: debugging
description: Use this skill when diagnosing and fixing bugs. It provides a structured approach to identify root causes and verify fixes.
---

# 🐛 Debugging

> **Philosophy:** A bug is a gift. It reveals a gap in your tests or understanding.

## Workflow

### 1. Reproduce
*   **First, reproduce the bug reliably.** If you can't reproduce it, you can't fix it.
*   Get exact steps, input, and environment.
*   Create a minimal test case that fails.

### 2. Isolate
*   **Narrow down the scope:** Frontend or Backend? Which function?
*   Use logging or debugger to inspect state at key points.
*   **Binary Search:** Comment out half the code. Does bug persist? Narrow down.

### 3. Diagnose
*   Ask: "What did I *expect*? What *actually* happened?"
*   Check recent changes (`git log`, `git blame`).
*   Inspect data entering and leaving suspect functions.

### 4. Fix & Verify
*   **Write a test that fails due to the bug.** (TDD for bugs!)
*   Implement the fix.
*   Run the test. **It MUST pass.**
*   Run full test suite to check for regressions.

### 5. Document
*   Add a comment explaining *why* the bug occurred.
*   If subtle, add to "Known Gotchas" in documentation.

## Common Bug Patterns
| Symptom | Likely Cause |
|---|---|
| Works locally, fails in CI | Environment differences, missing env vars |
| Works sometimes | Race condition, timing issue |
| Returns null/undefined | Missing null check, async timing |
| Wrong data displayed | API mismatch, caching issue |

## Examples
```
1. Bug: "Submit button does nothing."
2. Isolate: Is onClick firing? -> Add console.log.
3. Diagnose: Handler fires, but API returns 500.
4. Root Cause: Endpoint expects different payload format.
5. Fix: Update request payload. Add test.
```

## Guidelines
*   Never guess. Always verify with logs or debugger.
*   Don't just patch symptoms. Find the *root cause*.
*   If bug took >30 mins to find, add a test to prevent recurrence.
