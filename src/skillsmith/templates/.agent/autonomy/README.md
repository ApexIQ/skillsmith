# Autonomy Benchmarks

This folder holds benchmark templates for autonomy-oriented evaluation runs.

## What belongs here?
- Benchmark manifests that describe small, repeatable task sets.
- Task definitions that can be loaded by the runtime scorer without extra preprocessing.
- Brief notes explaining the intent of each benchmark pack.

## Schema rules
- Keep the top level small and stable: `name`, `description`, and `tasks`.
- Each task should have a stable `id` and a short `title`.
- Optional task fields may include `goal`, `expected_skills`, or other scorer-specific hints.
- Avoid deeply nested structures unless the scorer explicitly needs them.

## Recommendation tasks
The `benchmarks/recommendation_tasks.json` pack is the default template for recommendation-quality checks.

- Use it to benchmark whether the system recommends the right skills for a project scenario.
- Keep scenarios concrete and distinct.
- Prefer a few high-signal tasks over a large noisy set.

