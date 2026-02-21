# 🤖 AGENTS.md - Context & Instructions for AI Agents

> **Start Here:** This file is the primary entry point for AI Agents working on this project.

## 🧠 Prime Directives (The "Search-then-GSD" Protocol)

1.  **Read `.agent/STATE.md` First:** Orient yourself by reading the current project state.
2.  **Skill-First Discovery:** For any complex task, **SEARCH** `.agent/skills/` for the 2-3 most relevant instruction files. **READ** them before proposing a plan.
3.  **GSD Loop (The Agentic Loop):** Once armed with relevant skills, follow the structured loop:
    - **Discuss:** Clarify intent and edge cases.
    - **Plan:** Create a step-by-step implementation plan.
    - **Execute:** Write code and run tools.
    - **Verify:** Run tests and validate results.
4.  **Update State:** After every significant step, update `.agent/STATE.md`.

## 📂 Project Structure

- **`.agent/`**: Your brain. Stores skills, plans, and state.
    - **`skills/`**: "How-to" guides for specific tasks.
    - **`params/`**: Project-specific constraints.
    - **`PROJECT.md`**: High-level vision and tech stack.
    - **`ROADMAP.md`**: Strategic milestones.
    - **`STATE.md`**: Current tactical status.

## 🛠 Active Skills

Run `skillsmith list` to see available skills. specialized instructions are in `.agent/skills/`.
