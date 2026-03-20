# Recipe: CI Gate Flow (`doctor` + `eval`)

Goal: enforce a basic CI quality gate using built-in health and evaluation checks.

## Commands

```bash
skillsmith doctor --strict
skillsmith eval
skillsmith audit --strict
```

## Expected Result

- `doctor --strict` exits non-zero when setup drift exists.
- `eval` writes fresh artifacts under `.agent/evals/results/`.
- `audit --strict` exits non-zero when policy or integrity checks fail.

