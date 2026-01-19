---
version: 0.1.0
name: agentic-workflow
description: Use this skill when building agentic systems. Covers the agentic loop, tool usage, and iterative task execution patterns from Anthropic.
---

# 🔄 Agentic Workflow

> **Philosophy:** Agents gather context, take action, verify, and iterate until the goal is achieved.

## The Agentic Loop

Based on Anthropic's agent design patterns:

```
┌─────────────────────────────────────────────┐
│                                             │
│  1. GATHER CONTEXT                          │
│     └─ Read files, search, understand task  │
│                                             │
│  2. TAKE ACTION                             │
│     └─ Write code, run commands, edit files │
│                                             │
│  3. VERIFY RESULTS                          │
│     └─ Run tests, check output, validate    │
│                                             │
│  4. ITERATE OR COMPLETE                     │
│     └─ If not done, return to step 1        │
│                                             │
└─────────────────────────────────────────────┘
```

## Core Principles

### 1. Start Simple
*   Begin with a single-agent system.
*   Add complexity only when needed.
*   Maximize one agent's capabilities before adding more.

### 2. Clear Tool Contracts
Each tool should have:
*   **Clear input:** What parameters it accepts
*   **Clear output:** What it returns
*   **Error handling:** What happens on failure

```python
# Good tool definition
def search_codebase(query: str, file_pattern: str = "*") -> list[SearchResult]:
    """
    Search codebase for matching code.
    
    Args:
        query: Text or regex to search for
        file_pattern: Glob pattern to filter files (default: all)
    
    Returns:
        List of SearchResult with file, line, and content
    
    Raises:
        SearchError: If query is invalid regex
    """
```

### 3. Verification Before Completion

Never assume success. Always verify:

| Action | Verification |
|--------|--------------|
| File edit | Re-read file, check syntax |
| Code change | Run tests, check build |
| API call | Check response status |
| Command exec | Check exit code, read output |

## Workflow Patterns

### Sequential Processing
```
Task 1 → Task 2 → Task 3 → Done
```
**Use when:** Tasks have dependencies, order matters.

### Parallel Processing
```
     ┌─ Task A ─┐
     │          │
Start┼─ Task B ─┼─ Combine → Done
     │          │
     └─ Task C ─┘
```
**Use when:** Tasks are independent, speed matters.

### Evaluation Loop
```
Draft → Evaluate → Pass? → Done
  ↑                  │
  └────── No ────────┘
```
**Use when:** Quality matters, iterative improvement needed.

## Sub-Agent Pattern

For complex tasks, delegate to specialized sub-agents:

```
Main Agent (Orchestrator)
│
├── Coder Agent
│     Context: Source files, patterns
│     Tools: read_file, write_file, grep
│
├── Tester Agent
│     Context: Test files, coverage
│     Tools: run_tests, coverage_report
│
└── Reviewer Agent
      Context: Style guide, PR diff
      Tools: lint, security_scan
```

### When to Use Sub-Agents
*   Task requires >3 different contexts
*   Parallel execution would help
*   Different skills/tools needed per subtask

## CLAUDE.md / AGENTS.md

Create a project-level file for persistent agent context:

```markdown
# AGENTS.md

## Project Setup
uv sync && npm install

## Testing
pytest -v       # Backend tests
npm test        # Frontend tests

## Code Style
- Python: Black + Ruff
- TypeScript: Prettier + ESLint

## Architecture Notes
- Monorepo: /backend, /frontend, /shared
- API: FastAPI with versioned routes (/v1/)
```

## Anti-Patterns

| ❌ Don't | ✅ Do |
|---------|------|
| Skip verification | Always verify actions |
| One agent does everything | Delegate to sub-agents |
| Assume success | Check exit codes and outputs |
| Hardcode paths | Use dynamic discovery |

## Guidelines

*   **Fail fast:** Detect errors early, before compounding.
*   **Checkpoint often:** Save progress for long-running tasks.
*   **Log decisions:** Record why actions were taken.
*   **Timeout loops:** Set max iterations to prevent infinite loops.
