---
description: Structured review of recent code changes for regressions, security, and quality.
---

# [/review-changes] Code Review Checklist

## 1. Architectural Integrity
- [ ] Does it follow existing patterns in `src/`?
- [ ] Are the dependencies correctly pinned?
- [ ] Is it maintainable for senior engineers?

## 2. Security & Performance
- [ ] Are any secrets exposed?
- [ ] Are complexity limits avoided? (e.g., O(n^2) over large lists).

## 3. Tool Parity
- [ ] Are CLAUDE.md / GEMINI.md updated?
- [ ] Are relevant skills referenced?

// turbo
1. run_command { "CommandLine": "git diff main" }
2. run_command { "CommandLine": "ruff check" }
