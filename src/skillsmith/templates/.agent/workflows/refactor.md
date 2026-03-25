---
description: Perform safe, behavior-preserving code improvements with verification.
---

# [/refactor] Refactoring Lifecycle

## 1. Baseline State
- [ ] Run current test suite to ensure green baseline.
- [ ] Identify candidate code for refactoring (complex, duplicate, brittle).

## 2. Decoupling & Pattern Matching
- [ ] Apply 1:1 behavioral transformations.
- [ ] Align with existing modular patterns in `src/`.

## 3. Verification
- [ ] Run automated tests to prove equivalence.
- [ ] Run performance benchmarks if necessary.

// turbo
1. run_command { "CommandLine": "uv run pytest tests/" }
2. run_command { "CommandLine": "npx -y ruff check src/" }
