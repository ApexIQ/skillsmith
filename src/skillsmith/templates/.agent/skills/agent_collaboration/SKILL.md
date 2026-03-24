---
version: 0.1.0
name: agent-collaboration
description: Use this skill when coordinating multiple AI agents. Covers multi-agent patterns, handoffs, and orchestration strategies.
tags: [agents, multi-agent, orchestration, coordination]
---

# 🤝 Agent Collaboration

> **Philosophy:** Multiple specialized agents outperform one overloaded generalist.

## When to Use Multi-Agent

| Single Agent | Multiple Agents |
|--------------|-----------------|
| Focused task | Complex workflow |
| One context | Multiple contexts needed |
| Sequential work | Parallel execution benefits |
| <500 lines changed | Large-scale changes |

## Collaboration Patterns

### 1. Hub and Spoke (Orchestrator)

Central agent coordinates specialists:

```
           ┌── Coder ──┐
           │           │
Orchestrator── Tester ──├── Combine
           │           │
           └── Docs ───┘
```

**Use when:** Clear subtask boundaries, need coordination.

### 2. Pipeline (Sequential Handoff)

Each agent completes then passes to next:

```
Planner → Coder → Reviewer → Deployer
```

**Use when:** Each stage needs different expertise.

### 3. Debate (Adversarial)

Agents critique each other's work:

```
Proposer ←→ Critic → Improved Result
```

**Use when:** High stakes, quality critical, catching errors matters.

### 4. Swarm (Parallel Workers)

Multiple agents work on similar tasks:

```
     ┌─ Worker A (files 1-10) ─┐
Task ┼─ Worker B (files 11-20) ┼─ Merge
     └─ Worker C (files 21-30) ─┘
```

**Use when:** Embarrassingly parallel, same task type.

### 5. Recursive Decomposition (The Thinking Tree)

Based on [StructuredAgent (arXiv:2603.05294v1)](https://arxiv.org/html/2603.05294v1). Every goal is treated as a root node in a dynamic AND/OR thinking tree.

```
          [ Root Goal ]
          /           \
    [Plan A (OR)]      [Plan B (OR)]
     /        \          /        \
[Task 1] [Task 2]   [Task 1] [Task 2]
 [AND]    [AND]      [AND]    [AND]
```

**Orchestrator Protocol:**
- **Static vs. Dynamic**: Don't just follow a list. If Task 1 of Plan A fails, the orchestrator **prunes** Plan A and activates Plan B.
- **Node Injection**: If a new blocker is discovered, the orchestrator injects a new `AND` child into the tree to resolve the blocker before proceeding.
- **State Propagation**: Success in a leaf `AND` node propagates up to its parent `OR` node, satisfying the parent and concluding that branch of the search.

## Handoff Protocol

When passing work between agents:

```markdown
## Handoff: Coder → Reviewer

### Completed Work
- Added pagination to /users endpoint
- Updated UserService with new methods
- Modified files: routers/users.py, services/user_service.py

### Tests Status
- Unit tests: 5 new, all passing
- Integration: Not yet run

### Pending Actions
- [ ] Review for security issues
- [ ] Check pagination performance with large datasets
- [ ] Update API documentation

### Context for Reviewer
See: .agents/context/pagination_task.md
```

## Shared State

Agents need shared understanding:

### File-Based State
```
.agents/
├── state/
│   ├── current_task.md      # What we're doing
│   ├── decisions.md         # Choices made
│   └── blockers.md          # Current issues
```

### State Schema
```yaml
task:
  id: feat-pagination
  status: in_progress
  assigned_agent: coder
  
artifacts:
  - path: routers/users.py
    status: modified
    
blockers:
  - id: B001
    description: "Need DB index for performance"
    assigned: reviewer
```

## Communication Contracts

Define clear interfaces between agents:

```python
@dataclass
class TaskResult:
    """Standard result format for agent handoffs."""
    success: bool
    files_modified: list[str]
    tests_status: str  # "passing" | "failing" | "not_run"
    summary: str
    next_actions: list[str]
    context_file: str | None  # Path to detailed context
```

## Conflict Resolution

When agents disagree:

| Scenario | Resolution |
|----------|------------|
| Style disagreement | Defer to style guide |
| Architecture choice | Escalate to orchestrator |
| Both approaches valid | Document tradeoffs, pick one |
| Safety concern | Conservative choice wins |

## Anti-Patterns

| ❌ Don't | ✅ Do |
|---------|------|
| Agents talk in circles | Set max handoff count |
| Duplicate work | Clear ownership boundaries |
| Lose context in handoffs | Use structured handoff format |
| One agent blocks all | Parallel where possible |

## Guidelines

*   **Define roles:** Each agent has clear responsibility.
*   **Limit handoffs:** Each handoff loses context.
*   **Structured messages:** Use templates for handoffs.
*   **Shared memory:** Central files for cross-agent state.
*   **Timeout loops:** Max iterations for back-and-forth.
