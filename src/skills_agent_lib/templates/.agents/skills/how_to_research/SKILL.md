---
version: 0.1.0
name: how-to-research
description: Use this skill when exploring a new codebase or topic. It provides strategies for effective research.
---

# 🔍 How to Research

> **Rule:** Don't guess. Verify.

## 1. Internal Research (Codebase)
*   **Map the Territory:**
    *   List directory structure to understand organization.
    *   Read `README.md`, `package.json`, or `requirements.txt` first.
*   **Search Smart:**
    *   Use grep/ripgrep to find usage of functions/classes.
    *   Search for configuration files.
*   **Trace the Flow:**
    *   Start at the entry point (`main.py`, `index.tsx`, `app.ts`).
    *   Follow imports to understand dependencies.

## 2. External Research (Web)
*   **Query Engineering:**
    *   ✅ "FastAPI rate limiting middleware best practices 2024"
    *   ❌ "FastAPI slow"
*   **Trusted Sources:**
    *   Official documentation (React, FastAPI, etc.).
    *   GitHub Issues (for bug workarounds).
    *   Engineering Blogs (Uber, Netflix, Stripe for architecture).
    *   Stack Overflow (verify answers are up-to-date).

## 3. Synthesis
*   **Adapt, don't copy-paste.** Findings must fit *your* project context.
*   **Cite Sources:** Note where you found solutions in code comments.
*   **Cross-reference:** Verify information from multiple sources.

## Examples
*   **Understanding a new library:** Official docs -> GitHub examples -> Blog tutorials.
*   **Debugging an error:** Error message in quotes -> Search GitHub Issues -> Stack Overflow.

## Guidelines
*   Spend 5-10 mins researching before asking for help.
*   Document findings for future reference.
