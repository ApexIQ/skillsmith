---
name: context_optimization
description: Techniques to manage token usage and keep the Agent's brain fast.
version: 1.0.0
role: Architect
tags:
  - gsd
  - performance
  - tokens
---

# Context Optimization

"Context Rot" occurs when an Agent's context window fills with irrelevant history, causing it to forget early instructions or hallucinate. Use these strategies to stay sharp.

## 1. The "Repo Map" Strategy

Don't read every file. Use high-level maps.
- **Tree:** Run `tree` or `ls -R` to understand structure.
- **Signatures:** Read only function signatures/classes (using `grep` or `outline` tools) before reading full implementations.

## 2. Summarize & Flush

If the conversation gets too long (> 20 turns):
1.  **Summarize:** Compress all recent progress into `.agent/STATE.md`.
2.  **Flush:** Recommend the user start a new session/chat window.
    > "I have updated `STATE.md`. Please start a new chat and upload `STATE.md` to continue with a fresh context."

## 3. Target "Need-to-Know"

- **Don't** dump an entire 1000-line log into context.
- **Do** `grep` the log for "Error" or "Exception".
- **Don't** read `node_modules` or `venv`.

## 4. Artifact-Driven Memory

Never rely on "I told you 5 messages ago."
- If a decision is made, **write it down** in `.agent/decisions/ADR-001.md` or `.agent/PROJECT.md`.
- File contents are permanent; Chat history is ephemeral.
