---
name: project_state_management
description: Maintain clear project context and avoid hallucinations using GSD State Files.
version: 1.0.0
role: Project Manager
tags:
  - gsd
  - productivity
  - context-management
---

# Project State Management

This skill prevents "Context Rot" by maintaining a single source of truth for the project's state. AI Agents should read these files to understand *where we are* without re-reading the entire chat history.

## The State Files

1.  **`PROJECT.md`**: The high-level "Constitution" of the project.
2.  **`ROADMAP.md`**: The strategic plan (Features, Milestones).
3.  **`STATE.md`**: The tactical status (Current Task, Next Steps, Known Issues).

## 1. PROJECT.md (The "Why" and "What")

Create or update `.agent/PROJECT.md` with:

```markdown
# Project Name

## Vision
One sentence describing the ultimate goal.

## Tech Stack
- Language: Python/TypeScript
- Framework: FastAPI/Next.js
- Database: Postgres

## Core Principles
1.  Atomic Commits.
2.  Test-Driven Development.
3.  Mobile-First Design.
```

## 2. ROADMAP.md (The "When")

Create or update `.agent/ROADMAP.md` with:

```markdown
# Roadmap

## Phase 1: MVP [x]
- [x] User Authentication
- [x] Basic Dashboard

## Phase 2: Scale [/]
- [ ] Database Migration
- [ ] Redis Caching

## Phase 3: Polish [ ]
- [ ] UI Animations
- [ ] Dark Mode
```

## 3. STATE.md (The "Now")

**CRITICAL:** Update this file *after every atomic step*.

```markdown
# Current State

**Last Updated:** YYYY-MM-DD HH:MM

## Current Objective
Implementing the "Forgot Password" flow.

## Context
- We have the API endpoint `/auth/forgot`.
- We need the frontend form in `ForgotPassword.tsx`.

## Next Steps
1.  Create `ForgotPassword.tsx` form.
2.  Connect to API.
3.  Verify email delivery.
```

## Instructions for Agents

1.  **Start of Session:** Always read `STATE.md` to orient yourself.
2.  **End of Task:** Always update `STATE.md` with your progress.
3.  **Confusion:** If `STATE.md` contradicts the code, trust the code but update `STATE.md` immediately.
