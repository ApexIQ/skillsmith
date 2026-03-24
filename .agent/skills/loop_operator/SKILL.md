---
version: 1.0.0
name: loop-operator
description: Use this skill when executing autonomous or semi-autonomous agent loops. Covers bounded execution, safety guards, checkpoint/resume patterns, progress tracking, and graceful termination for long-running agentic workflows.
---

# 🔄 Loop Operator — Autonomous Execution with Safety

> **Philosophy:** Autonomous loops are powerful but dangerous. Every loop must have a clear exit condition, a safety budget, and a checkpoint mechanism. Unbounded loops are bugs, not features.

## 1. When to Use This Skill

- Running multi-step agentic workflows autonomously
- Processing batches of tasks (files, tests, migrations)
- Implementing retry logic with exponential backoff
- Building CI/CD pipeline stages
- Any iterative process that needs bounded execution

## 2. The Autonomous Loop Contract

Every autonomous loop MUST have these 5 properties:

| Property | Description | Example |
|----------|------------|---------|
| **Exit Condition** | When does the loop stop successfully? | All tests pass, all files processed |
| **Max Iterations** | Hard cap on loop cycles | max_iterations=50 |
| **Max Duration** | Hard cap on wall-clock time | max_hours=2 |
| **Failure Budget** | How many consecutive failures before abort | early_stop_fails=3 |
| **Checkpoint** | State saved after each iteration for resume | checkpoint_dir=.agent/loops/ |

### The Bounded Loop Template

```python
import time
import json
from pathlib import Path

class BoundedLoop:
    def __init__(
        self,
        max_iterations: int = 50,
        max_duration_seconds: int = 7200,
        early_stop_fails: int = 3,
        checkpoint_dir: str = ".agent/loops",
    ):
        self.max_iterations = max_iterations
        self.max_duration_seconds = max_duration_seconds
        self.early_stop_fails = early_stop_fails
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.iteration = 0
        self.consecutive_failures = 0
        self.start_time = time.time()
        self.results = []
    
    def should_continue(self) -> bool:
        """Check all exit conditions."""
        if self.iteration >= self.max_iterations:
            print(f"⛔ Max iterations reached ({self.max_iterations})")
            return False
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.max_duration_seconds:
            print(f"⛔ Max duration reached ({self.max_duration_seconds}s)")
            return False
        
        if self.consecutive_failures >= self.early_stop_fails:
            print(f"⛔ Too many consecutive failures ({self.early_stop_fails})")
            return False
        
        return True
    
    def checkpoint(self, state: dict):
        """Save state for resume capability."""
        checkpoint = {
            "iteration": self.iteration,
            "elapsed_seconds": time.time() - self.start_time,
            "consecutive_failures": self.consecutive_failures,
            "state": state,
            "results": self.results,
        }
        path = self.checkpoint_dir / "latest.json"
        path.write_text(json.dumps(checkpoint, indent=2))
    
    def record_result(self, success: bool, details: dict):
        """Track iteration outcomes."""
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
        
        self.results.append({
            "iteration": self.iteration,
            "success": success,
            "details": details,
        })
        self.iteration += 1
```

## 3. Loop Patterns

### Pattern 1: Fix-Verify Loop

The most common agentic pattern — fix something, verify the fix, repeat:

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│ Analyze │────▶│  Fix    │────▶│ Verify   │
│ Error   │     │ Issue   │     │ Fix      │
└─────────┘     └─────────┘     └────┬─────┘
     ▲                               │
     │          ┌──────────┐         │
     └──────────│  Failed  │◀────────┘
                └──────────┘    Pass ──▶ ✅ Done
```

**Rules:**
- Max 5 fix attempts per issue before escalating to human
- Each attempt must try a DIFFERENT fix (no repeating the same fix)
- Track what was tried so you don't loop

### Pattern 2: Batch Processing Loop

Process a list of items with progress tracking:

```python
items = get_items_to_process()
total = len(items)

for i, item in enumerate(items):
    if not loop.should_continue():
        break
    
    print(f"[{i+1}/{total}] Processing {item.name}...")
    
    try:
        result = process(item)
        loop.record_result(True, {"item": item.name})
    except Exception as e:
        loop.record_result(False, {"item": item.name, "error": str(e)})
    
    loop.checkpoint({"last_processed": item.name, "remaining": total - i - 1})

print(f"✅ Processed {loop.iteration}/{total} items")
```

### Pattern 3: Convergence Loop

Run until output stabilizes (e.g., linting, formatting):

```python
previous_hash = None

while loop.should_continue():
    run_formatter()
    current_hash = hash_of_output()
    
    if current_hash == previous_hash:
        print("✅ Output converged — no more changes")
        break
    
    previous_hash = current_hash
    loop.record_result(True, {"hash": current_hash})
    loop.checkpoint({"hash": current_hash})
```

### Pattern 4: Progressive Refinement Loop

Each iteration improves the output quality:

```
Iteration 1: Generate rough draft       (quality: 40%)
Iteration 2: Fix errors, add detail     (quality: 65%)
Iteration 3: Polish, optimize           (quality: 80%)
Iteration 4: Final review               (quality: 90%)
Exit: Quality threshold met ✅
```

**Rule:** If quality score doesn't increase for 2 consecutive iterations, stop — you've hit diminishing returns.

## 4. Safety Guards

### Guard 1: Resource Limits
```python
import resource

# Limit memory to 2GB
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))

# Limit CPU time to 1 hour
resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
```

### Guard 2: Mutation Safety

```python
# Before any destructive operation, snapshot current state
def safe_mutate(operation, rollback):
    snapshot = capture_state()
    try:
        result = operation()
        if not verify_result(result):
            rollback(snapshot)
            raise ValueError("Result verification failed")
        return result
    except Exception:
        rollback(snapshot)
        raise
```

### Guard 3: Cost Budget

```python
# Track token/API costs per iteration
cost_budget = 10.00  # $10 max
total_cost = 0.0

for iteration in loop:
    iteration_cost = estimate_cost(iteration)
    if total_cost + iteration_cost > cost_budget:
        print(f"⛔ Cost budget exceeded (${total_cost:.2f}/${cost_budget:.2f})")
        break
    total_cost += iteration_cost
```

### Guard 4: Git Clean Check

```bash
# Never run autonomous loops on dirty git trees
if [ -n "$(git status --porcelain)" ]; then
    echo "⛔ Git tree is dirty. Commit or stash changes first."
    exit 1
fi
```

## 5. Resume & Recovery

```python
def resume_from_checkpoint(checkpoint_dir):
    """Resume a loop from the last checkpoint."""
    checkpoint_file = Path(checkpoint_dir) / "latest.json"
    if not checkpoint_file.exists():
        return None  # Fresh start
    
    checkpoint = json.loads(checkpoint_file.read_text())
    print(f"📂 Resuming from iteration {checkpoint['iteration']}")
    return checkpoint

# Usage
checkpoint = resume_from_checkpoint(".agent/loops")
if checkpoint:
    start_from = checkpoint["state"]["last_processed"]
    items = get_remaining_items(after=start_from)
else:
    items = get_all_items()
```

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| `while True:` with no exit | Always have max_iterations + max_duration |
| No checkpoint/resume | Save state after every iteration |
| Retrying same fix repeatedly | Track attempts, try different strategies |
| No cost tracking | Budget tokens/API calls per loop |
| Running on dirty git tree | Require clean git state before starting |
| Swallowing errors silently | Log every failure, track consecutive failures |

## Guidelines

- **Every loop gets a budget.** Time, iterations, cost — at least one hard limit.
- **Checkpoint after every iteration.** Users will Ctrl+C. Your loop must survive it.
- **Different fix each attempt.** If you're doing the same thing expecting different results, you're in an infinite loop.
- **Clean state before starting.** Git clean, no uncommitted work, fresh logs.
- **Report progress.** Users need to know the loop is making progress, not stuck.
- See `agentic-workflow` skill for broader agentic execution patterns.
- See `debugging` skill for diagnosing issues within loop iterations.
