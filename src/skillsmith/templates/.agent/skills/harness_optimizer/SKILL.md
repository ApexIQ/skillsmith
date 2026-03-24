---
version: 1.0.0
name: harness-optimizer
description: Use this skill when tuning AI agent configurations for performance, cost, and reliability. Covers token optimization, context window management, model selection, prompt engineering for agents, and cost-per-task reduction strategies.
---

# ⚡ Harness Optimizer — Tune Your Agent for Peak Performance

> **Philosophy:** The best agent configuration is the one that ships the most correct code per dollar spent. Optimize for outcome-per-token, not raw capability.

## 1. When to Use This Skill

- Agent token costs are too high
- Agent is hitting context window limits
- Agent performance is inconsistent or degrading
- Switching between models for different tasks
- Setting up a new project's agent configuration
- Debugging why agent quality has dropped

## 2. Token Cost Optimization

### The Token Budget Framework

| Task Type | Recommended Model | Context Budget | Target Cost |
|-----------|------------------|----------------|-------------|
| Simple code edits | Fast/small model | 8K tokens | $0.01-0.05 |
| Code review | Medium model | 16K tokens | $0.05-0.20 |
| Architecture design | Best available model | 32K tokens | $0.20-1.00 |
| Complex debugging | Best available model | 64K tokens | $0.50-2.00 |
| Documentation | Medium model | 16K tokens | $0.05-0.15 |
| Test generation | Medium model | 32K tokens | $0.10-0.30 |

### Cost Reduction Strategies

#### Strategy 1: Tiered Model Routing
```yaml
# Route tasks to the cheapest model that can handle them
routing:
  simple_edits:
    model: claude-3-haiku     # Cheapest
    max_tokens: 4096
  code_review:
    model: claude-3.5-sonnet  # Mid-tier
    max_tokens: 8192
  architecture:
    model: claude-3.5-opus    # Premium — only when needed
    max_tokens: 16384
```

#### Strategy 2: Context Compression
```markdown
## Before (wasteful — 2000 tokens)
Here is the entire file contents of user_service.py:
[... 200 lines of code ...]
Please fix the bug on line 45.

## After (efficient — 400 tokens)
In user_service.py, the `create_user` method (lines 40-55):
```python
def create_user(self, data):
    # BUG: missing email validation
    user = User(**data)
    self.db.save(user)
```
Fix: add email validation before line 43.
```

#### Strategy 3: Result Caching
```python
# Cache expensive operations
# Don't re-analyze unchanged files
cache = load_cache(".agent/context/recall_cache.json")

if file_hash == cache.get(file_path, {}).get("hash"):
    # File hasn't changed — reuse previous analysis
    return cache[file_path]["result"]
else:
    # File changed — re-analyze
    result = analyze(file_path)
    cache[file_path] = {"hash": file_hash, "result": result}
    save_cache(cache)
```

#### Strategy 4: Progressive Context Loading
```
Step 1: Load project summary only (500 tokens)
Step 2: If insufficient, load relevant module (2K tokens)
Step 3: If still insufficient, load full file (5K tokens)
Step 4: Only if necessary, load related files (10K+ tokens)
```

## 3. Context Window Management

### The Context Priority Stack

Load context in this order — stop when you have enough:

| Priority | What to Load | Typical Size |
|----------|-------------|-------------|
| P0 | Current task description | 100-500 tokens |
| P1 | Active file being edited | 500-2K tokens |
| P2 | Project profile + rules | 500-1K tokens |
| P3 | Relevant skill instructions | 500-2K tokens |
| P4 | Related files (imports, tests) | 1K-5K tokens |
| P5 | Project context index results | 1K-3K tokens |
| P6 | Full codebase scan | 5K-50K tokens |

**Rule:** Most tasks need only P0-P3. Loading P6 for a simple edit is a 100× cost overrun.

### Context Window Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent "forgets" earlier instructions | Context overflow | Compress or paginate context |
| Agent repeats itself | Past output filling context | Clear/compact conversation history |
| Agent quality drops mid-conversation | Important context pushed out | Re-inject key context periodically |
| Agent invents non-existent APIs | Insufficient context | Load the actual API signatures |

### Compaction Strategies

```markdown
## When to Compact
- Conversation exceeds 50% of context window
- Agent starts repeating or contradicting itself
- Switching to a new subtask

## How to Compact
1. Summarize completed work (what was done, what decisions were made)
2. Keep: current task, active files, key decisions
3. Drop: exploration that didn't lead anywhere, verbose error outputs
4. Re-inject: project rules, skill instructions (these get lost first)
```

## 4. Agent Configuration Best Practices

### AGENTS.md / CLAUDE.md Optimization

```markdown
# GOOD: Concise, actionable rules (300 tokens)
## Rules
1. Write tests before implementation (TDD).
2. Maximum file length: 300 lines. Split if longer.
3. Every function needs a docstring with Args/Returns/Raises.
4. No hardcoded secrets. Use environment variables.
5. Run `pytest` after every code change.

# BAD: Verbose, vague rules (3000 tokens)
## Rules
When writing code, you should always think about testing first.
This means that ideally you would write your tests before writing
the implementation code. This is known as Test-Driven Development
or TDD for short. The basic idea is that... [continues for 500 words]
```

**Rule:** Agent rules should be dense instructions, not tutorials. Every word costs tokens on every request.

### Skill Loading Optimization

```yaml
# .agent/project_profile.yaml
# Only load skills relevant to this project
languages:
  - python          # → loads python-expert skill
frameworks:
  - fastapi         # → loads fastapi-best-practices skill
priorities:
  - testability     # → loads TDD skill
  - security        # → loads security-audit skill
```

**Don't load:** Go skills for a Python project. Frontend skills for a CLI tool. Database skills when there's no database.

## 5. Performance Monitoring

### Key Metrics to Track

| Metric | Good | Warning | Bad |
|--------|------|---------|-----|
| Tokens per task | < 5K | 5K-20K | > 20K |
| Cost per task | < $0.10 | $0.10-0.50 | > $0.50 |
| First-attempt success | > 80% | 60-80% | < 60% |
| Context utilization | 30-70% | 70-90% | > 90% |
| Skill hit rate | > 70% | 50-70% | < 50% |

### Monitoring Commands

```bash
# Check current budget usage
skillsmith budget

# Review skill effectiveness
skillsmith metrics

# Get optimization suggestions
skillsmith suggest

# Full performance audit
skillsmith eval --benchmark standard
```

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| Loading entire codebase as context | Progressive context loading (P0→P6) |
| Using the biggest model for everything | Tiered model routing by task type |
| 2000-word system prompts | Dense, actionable rules (< 500 tokens) |
| Never compacting conversation | Compact at 50% context utilization |
| Loading all skills for every task | Profile-driven skill selection |
| No cost tracking | Monitor tokens/cost per task daily |

## Guidelines

- **Measure before optimizing.** Run `skillsmith budget` to see where tokens go.
- **Compress context, not quality.** Give agents precise information, not less information.
- **Profile-driven everything.** Let the project profile determine what gets loaded.
- **Re-inject, don't assume.** Agent memory is finite — re-inject important rules explicitly.
- **Cost is a feature.** Track cost-per-task as a first-class metric alongside correctness.
- See `context-engineering` skill for advanced context window strategies.
- See `prompt-engineering` skill for crafting efficient agent instructions.
