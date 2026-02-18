---
name: atomic_execution
description: Standardized "Plan -> Execute -> Verify" workflow for Agentic coding.
version: 1.0.0
role: Senior Engineer
tags:
  - gsd
  - workflow
  - best-practices
---

# Atomic Execution Workflow

Use this workflow for **every** coding task to ensure quality and prevent "Agent Hallucinations".

## The Loop

1.  **Discuss (Review)**
2.  **Plan**
3.  **Execute**
4.  **Verify**

---

## 1. Discuss (Review)

Before writing code, understand the context.
- Read `.agent/STATE.md`.
- Read relevant source files.
- Ask clarifying questions if requirements are vague.

## 2. Plan (The Blueprints)

Create a specific plan for *this specific task*. Do not generic plan.
- **For complex tasks:** Create/Update `.agent/plans/current_task.md`.
- **For simple tasks:** Output a markdown checklist in the chat.

**Checklist Format:**
```markdown
- [ ] Create `file_a.py` with function `x`.
- [ ] Update `file_b.py` to import `x`.
- [ ] Run test `test_x.py` to verify.
```

## 3. Execute (Atomic Steps)

Write code in small, verifiable chunks.
- **Do not** write 5 files at once.
- **Do** write one module, then the next.
- **Do** use `edit_file` or `write_file` tools precisely.
- **Rule:** If you edit a file, you *must* know its current content (read it first).

## 4. Verify (Trust, but Verify)

**Never** claim a task is done without proof.
- **Compile/Lint:** Run the build command.
- **Test:** Run specific unit tests (`pytest tests/test_feature.py`).
- **Manual Check:** If UI, verify the component renders (conceptually or via screenshots if available).

## Completion

Once verified:
1.  Update `.agent/STATE.md`.
2.  Mark the item as done in `.agent/ROADMAP.md` (if applicable).
3.  Notify the user.
