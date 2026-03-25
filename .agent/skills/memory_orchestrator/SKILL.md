---
version: 0.1.0
name: memory-orchestrator
description: Implementation of the "Five-Layer Memory Reliability Pattern" (arXiv/OpenSpace Inspired).
  Covers observer-reflector-recovery-watcher-safeguard pipelines for cost-efficient AI agents.
  This skill implements the project's Memory and Cost Policy.
tags:
- memory
- cost
- context
- compacting
- agents
- sessions
- lessons
- patterns
globs:
- '**/*.py'
- '.agent/logs/**'
- '.agent/lessons.md'
---

# 🧠 Memory Orchestrator (O3-RS Pipeline)

> **Directive:** "Library-First. Context-Lean. Multi-Layer Recovery."

## The Five-Layer Reliability Pattern

To achieve 100% project recall at <50% token cost, implement these layers in strict sequence:

### 1. 👁️ Layer 1: Observer Capture (Raw Event Log)
**Goal:** Record all agent actions without interrupting reasoning.
- **Pattern:** `ObserverPattern` or `EventStore`.
- **Implementation:** Intercept all tool calls/outputs and prompt responses.
- **Storage:** Append-only `raw_events.jsonl` in `.agent/logs/`.
- **Logic:** Never summarize in real-time; storage is cheap, reasoning is expensive.

### 2. 🪞 Layer 2: Reflector Compaction (Cognitive Compression)
**Goal:** Distill facts from raw events.
- **Trigger:** End of task or `token_count > N`.
- **Pattern:** `MapReduce` for memories.
- **Implementation:** Call a cheaper LLM (e.g., GPT-4o-mini) to extract **Lessons (what to do next time)** and **Observations (what happened)**.
- **Storage:** Structured `lessons.md` or `observations.json`.

### 3. 🏁 Layer 3: Session Recovery (Relevance Injection)
**Goal:** Hydrate the current session with only the "Best-of-Best" context.
- **Pattern:** `PersistentRetrievalAugmentedGeneration (P-RAG)`.
- **Implementation:** Query the local `index.json` using BM25 or keywords from the current goal. 
- **Constraint:** Max 2-3 "Lessons" and top-5 "Recent Observations" per prompt.

### 4. ⚡ Layer 4: Reactive Watcher Refresh (Drift Guard)
**Goal:** Ensure memory is not hallucinating based on old code.
- **Pattern:** `Watcher` + `Fingerprinting`.
- **Implementation:** Link memory chunks to file paths + SHA-256 hashes.
- **Invalidation:** If the file system changes, flag related memories as "Stale" or "Needs Re-reflection".

### 5. 🛡️ Layer 5: Pre-compaction Safeguard (Context Bound)
**Goal:** Prevent total context amnesia.
- **Pattern:** `BoundedBuffer` or `PriorityQueue`.
- **Implementation:** A simple token counter that forces a mandatory "Reflector" run when context reaches 80% to ensure critical info is persisted before it overflows.

## Cost-Effective Guidelines

| Tier | Model | Strategy |
|:---|:---|:---|
| **L1 (Capture)** | 0 tokens | Local file system append |
| **L2 (Reflect)** | Cheap LLM | Many small summarizations |
| **L3 (Reason)** | Premium LLM | Ground with hydrated context |
| **L4 (Verify)** | 0 tokens | Local hashing (SHA-256) |

---

## 🚫 Anti-Patterns to Avoid
- `❌ DON'T`: Keep full conversation history for >5 turn sessions.
- `❌ DON'T`: Reflect every turn (too expensive).
- `❌ DON'T`: Use premium models for summarization.
- `✅ DO`: Use `lessons.md` as the "Permanent Brain" for the repository.

## 🏆 Success Metrics
1. **Recall Delta**: Success rate of tasks where context was hydrated vs raw.
2. **Token Efficiency**: (Total Words in Session) / (Tokens Used by LLM). Aim for > 0.8.
