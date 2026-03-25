---
description: Run test suites and verify performance/readiness metrics.
---

# [/test-changes] Verification Suite

## 1. Automated Tests
- [ ] Run `uv run pytest -v`.
- [ ] Check coverage reports.

## 2. Regression Testing
- [ ] Check related modules / consumers.
- [ ] Verify existing functionality in `ghost_test_lab` (if applicable).

## 3. Readiness Check
- [ ] Run `skillsmith ready`.
- [ ] Run `skillsmith doctor`.

// turbo
1. run_command { "CommandLine": "python -m unittest discover tests -v" }
2. run_command { "CommandLine": "skillsmith ready" }
