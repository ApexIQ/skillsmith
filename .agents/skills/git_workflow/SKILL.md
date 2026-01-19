---
version: 0.1.0
name: git-workflow
description: Use this skill for version control best practices. It defines branching, commit messages, and PR conventions.
---

# 🌳 Git Workflow

> **Rule:** Good git hygiene makes debugging and collaboration 10x easier.

## 1. Branching Strategy
| Branch | Purpose | Merges To |
|---|---|---|
| `main` | Production-ready code | - |
| `develop` | Integration branch | `main` |
| `feature/<name>` | New features | `develop` |
| `fix/<name>` | Bug fixes | `develop` or `main` (hotfix) |

*   **Naming:** `feature/add-command-palette`, `fix/email-sync-timeout`.

## 2. Commit Messages (Conventional Commits)
```
<type>(<scope>): <short description>

<body - optional>
```

| Type | Use Case |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that doesn't fix a bug or add a feature |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Build process, dependencies |

**Examples:**
*   `feat(inbox): add command palette (Cmd+K)`
*   `fix(sync): handle timeout errors gracefully`
*   `refactor(rules): extract validation logic to service`

## 3. Pull Request Conventions
*   **Title:** Same format as commit message.
*   **Description:**
    *   **What:** 1-2 sentences on the change.
    *   **Why:** Link to issue/task.
    *   **How to test:** Steps for reviewer.
*   **Size:** <300 lines. Larger PRs should be split.

## Examples
*   **Good PR:** `feat(dashboard): add priority radar component` - 150 lines, tests included.
*   **Bad PR:** `updates` - 800 lines, no description, touches 20 files.

## Guidelines
*   Commit often, push daily.
*   Rebase feature branches on `develop` before PR.
*   Squash commits when merging to keep history clean.
