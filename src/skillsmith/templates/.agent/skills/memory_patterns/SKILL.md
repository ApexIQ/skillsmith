---
version: 0.1.0
name: memory-patterns
description: Use this skill when managing agent context and memory. Covers short-term vs long-term memory, context compaction, and persistent note-taking patterns.
tags: [memory, context, agents, persistence, notes]
---

# 🧠 Memory Patterns

> **Philosophy:** Agents are stateless by default. Good memory design makes them context-aware and consistent.

## The Problem

LLMs have finite context windows and no built-in memory across sessions. Without proper patterns:
- Agents forget past decisions
- Context overflow causes quality degradation
- Token costs increase unnecessarily

## Memory Types

| Type | Description | Implementation |
|------|-------------|----------------|
| **Short-term** | Current conversation context | Prompt + recent messages |
| **Long-term** | Persistent across sessions | Files, databases, vector stores |
| **Episodic** | Specific past experiences | Indexed conversation logs |
| **Semantic** | Facts and knowledge | RAG with embeddings |

## Patterns

### 1. Structured Note-Taking (CLAUDE.md / AGENTS.md)

Store important context in project files:

```markdown
# CLAUDE.md

## Key Decisions
- Using SQLModel for ORM (decided 2024-01-15)
- API versioning via URL path (/v1/, /v2/)

## Gotchas
- `email_id` is string (Gmail format), not integer
```

**When to use:** Project-specific knowledge, conventions, past decisions.

### 2. Context Compaction

Summarize long conversations to preserve tokens:

```
Original: [3000 tokens of back-and-forth]
Compacted: "User requested auth system. Decided on JWT + refresh tokens. 
           Implemented /login and /refresh endpoints. Tests passing."
```

**When to use:** Long-running tasks, before context window fills.

### 3. Hierarchical Memory (Sub-agent Pattern)

Delegate tasks to sub-agents with focused context:

```
Main Agent (high-level context)
├── Code Agent (code-only context)
├── Test Agent (test files context)
└── Doc Agent (documentation context)
```

**When to use:** Large codebases, parallel tasks, complex workflows.

### 4. File System as Memory

Use files to persist information beyond context:

```
.agents/
├── decisions/         # ADRs and key decisions
├── notes/             # Temporary working notes
└── context/           # Current task context
```

**When to use:** Multi-session work, team collaboration.

## Anti-Patterns

| ❌ Don't | ✅ Do |
|---------|------|
| Keep everything in context | Store persistent info in files |
| Repeat full history each turn | Summarize and compact |
| One giant agent | Delegate to specialized sub-agents |
| Lose important decisions | Document in CLAUDE.md / AGENTS.md |

## Guidelines

*   **Offload early:** Move important context to files before window fills.
*   **Summarize often:** Compress long conversations to key points.
*   **Persist decisions:** Any decision that took >5 mins to make goes in docs.
*   **Use structure:** Organized files are easier to retrieve than raw logs.
