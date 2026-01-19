---
version: 0.1.0
name: refactoring-patterns
description: Use this skill when improving existing code without changing its behavior. It defines when and how to refactor safely.
---

# ♻️ Refactoring Patterns

> **Rule:** Refactor with tests. No tests = No refactor.

## 1. When to Refactor
| Signal | Action |
|---|---|
| Same code in 3+ places | Extract to function/component. |
| Function >50 lines | Split into smaller functions. |
| File >500 lines | Split into modules. |
| "I don't understand this" | Add comments, then simplify. |

**When NOT to Refactor:**
*   No tests covering the code.
*   Deadline pressure (ship first, refactor later).
*   "Just because" - there must be a clear benefit.

## 2. Common Refactoring Patterns

### Extract Function
```python
# Before
def process_email(email):
    # 50 lines of validation
    # 50 lines of processing

# After
def process_email(email):
    validate_email(email)
    transform_email(email)
```

### Extract Component (React)
```tsx
// Before: 200-line component
// After: Split into <EmailList />, <EmailRow />, <EmailActions />
```

### Replace Magic Numbers
```python
# Before
if priority > 7:

# After
HIGH_PRIORITY_THRESHOLD = 7
if priority > HIGH_PRIORITY_THRESHOLD:
```

### Introduce Parameter Object
```python
# Before
def send_email(to, subject, body, cc, bcc, attachments): ...

# After
def send_email(request: SendEmailRequest): ...
```

## 3. Safe Refactoring Workflow
1.  **Write tests** (if they don't exist).
2.  **Run tests** - they should pass.
3.  **Refactor** in small steps.
4.  **Run tests after each step.**
5.  **Commit** when green.

## Examples
*   **Good refactor:** Extract `calculatePriority()` from a 100-line function. Tests pass before and after.
*   **Bad refactor:** "Cleaned up" a file with no tests. Shipped a bug.

## Guidelines
*   One refactor per commit. Don't mix refactors with features.
*   Use IDE refactoring tools (Rename, Extract) - they're safer.
*   If refactor is risky, create a feature flag to roll back.
