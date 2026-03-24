---
version: 0.1.0
name: context-engineering
description: Use this skill for optimizing AI context windows. Covers context sizing, prioritization, and avoiding context overflow.
tags: [ai, context, memory, tokens, optimization]
---

# 🎯 Context Engineering

> **Philosophy:** The right context at the right time produces the best results.

## The Problem

AI models have limited context windows:
*   Too little context → Hallucinations, wrong assumptions
*   Too much context → Quality degradation, high costs
*   Wrong context → Irrelevant or incorrect output

## Context Window Management

### Know Your Limits

| Model | Approx Context | Practical Limit |
|-------|----------------|-----------------|
| GPT-4 | 128k tokens | ~80k for best quality |
| Claude 3.5 | 200k tokens | ~150k for best quality |
| Gemini 2.0 | 1M+ tokens | ~500k for best quality |

**Rule of thumb:** Stay at 50-70% of max for optimal performance.

### Context Priority Stack

Order context by importance:

```
1. CRITICAL: Current task instructions
2. HIGH: Directly relevant code/files
3. MEDIUM: Related patterns/examples
4. LOW: General project context
5. OPTIONAL: Historical context
```

## Strategies

### 1. Progressive Disclosure

Start minimal, add context as needed:

```
Step 1: Give task + key file
Step 2: Agent asks for more context
Step 3: Provide specific additional files
Step 4: Agent completes task
```

### 2. Context Windowing

Show only relevant sections:

```python
# ❌ Don't: Load entire 5000-line file
file_content = read_file("huge_file.py")

# ✅ Do: Load only relevant section
file_content = read_file("huge_file.py", start=100, end=200)
```

### 3. Semantic Chunking

Include related code, not arbitrary ranges:

```
Good chunk: Entire function + its imports
Bad chunk: Lines 100-200 (arbitrary)
```

### 4. Context Prefetching

Anticipate needs based on task type:

| Task Type | Prefetch |
|-----------|----------|
| Bug fix | Error logs, related tests, recent changes |
| New feature | Similar features, API patterns, tests |
| Refactor | Callers, tests, type definitions |

## Context Organization

Structure context for clarity:

```markdown
<current_file>
[The file being edited]
</current_file>

<related_files>
[Files that import/use current_file]
</related_files>

<tests>
[Test files for current functionality]
</tests>

<documentation>
[API docs, READMEs relevant to task]
</documentation>
```

## Signs of Context Problems

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Hallucinated imports | Missing file context | Add import sources |
| Wrong API usage | Missing API docs | Add documentation |
| Inconsistent patterns | Missing examples | Add similar code |
| Forgets earlier work | Context too long | Summarize, start fresh |

## Anti-Patterns

| ❌ Don't | ✅ Do |
|---------|------|
| Dump entire codebase | Curate relevant files |
| Include build artifacts | Focus on source code |
| Keep stale context | Refresh for each task |
| Mix unrelated tasks | One task = one context |

## Guidelines

*   **Measure:** Track token usage to understand patterns.
*   **Prune:** Remove context that isn't being used.
*   **Segment:** Separate context types with clear delimiters.
*   **Refresh:** Start fresh contexts for new tasks.
*   **Index:** Use search/grep rather than loading everything.
