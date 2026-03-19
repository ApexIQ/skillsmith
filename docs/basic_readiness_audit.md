# Basic Readiness Audit

Date: 2026-03-20  
Scope: Package-management basics, workflow-management sanity, and docs/API surface consistency.

## Executive Verdict

- Overall: `ON TRACK`, but with `BASIC READINESS GAPS` that should be fixed before building more features.
- Recommendation: `Pause new feature work` and run a short docs/packaging hardening sprint (1-3 days).

## Pass/Fail Summary

| Area | Status | Notes |
| --- | --- | --- |
| Packaging metadata core | Pass | `pyproject.toml` has name/version/readme/requires-python/authors/classifiers/dependencies/scripts. |
| Build command baseline | Partial | `uv run python -m build` fails (`No module named build`) in current env. |
| Fresh install smoke | Pass | Offline local install into fresh venv succeeded; `skillsmith --help` works. |
| CLI entrypoint | Pass | Console script works; module entrypoint is `python -m skillsmith`. |
| Flow 1 (`init -> discover/add -> compose -> eval`) | Pass | All commands returned exit code `0`; workflow and eval artifacts created. |
| Flow 2 (service auth/tenant boundaries) | Pass | `401` for missing token, `403` for cross-tenant access, scoped behavior works. |
| Flow 3 (trust warning path) | Pass | `audit --json` surfaces revoked-key trust warnings correctly. |
| README command coverage | Fail | README is stale/incomplete vs real CLI command surface. |
| README run-from-source command | Fail | Uses `python -m skillsmith.cli` instead of `python -m skillsmith`. |
| Library vs CLI contract clarity | Fail | Public import/API stability boundaries not clearly documented. |

## What Is Missing at Basic Level

1. README drift against real commands (`align`, `sync`, `report`, `profile`, `audit`, `eval`, `rebuild`, `context-index/context`, `registry`, `registry-service`, `trust-service`).
2. Incorrect module-run example in README.
3. Stale version text in README (`0.5.2` vs current `0.6.1`).
4. No explicit statement on whether this package is CLI-first only or supports stable Python import APIs.
5. `build` package is not available in the default dev environment used for `python -m build`.
6. `license` field is not explicitly set in `[project]` despite license classifier.

## Evidence (Key Commands)

- Packaging:
  - `uv run python -m build` -> failed (`No module named build`)
  - Fresh venv offline install -> passed
  - `skillsmith --help` in fresh venv -> passed
- Workflow:
  - `python -m skillsmith init --minimal` -> passed
  - `python -m skillsmith discover ... --source local` -> passed
  - `python -m skillsmith add ...` -> passed
  - `python -m skillsmith compose ...` -> passed
  - `python -m skillsmith eval` -> passed
  - service auth and tenant checks -> passed (`401`/`403` behavior verified)
  - `python -m skillsmith audit --json` -> trust warnings surfaced correctly

## Decision: Build More or Fix Basics First

- Immediate choice: `Fix basics first`.
- Reason: runtime and governance are working, but operator clarity (docs/API contract) and packaging hygiene are lagging and will cause adoption friction.

## Next 7 Actions (Priority Order)

1. Update README command surface to match `src/skillsmith/cli.py` exactly.
2. Fix README module invocation to `python -m skillsmith`.
3. Update README version/status block to match package version.
4. Add a short "Library vs CLI Support Contract" section in README.
5. Add `build` to dev tooling path or document the preferred build command via `uv build`/hatch path.
6. Add explicit `license = { text = "MIT" }` (or file-based) to `[project]`.
7. Re-run this audit after docs/packaging fixes and record a green baseline.

## Remediation Status (2026-03-20)

- Done: README command surface updated to match current CLI.
- Done: README module invocation corrected to `python -m skillsmith`.
- Done: README package version/status refreshed to `0.6.1`.
- Done: README now includes explicit CLI-vs-library support contract.
- Done: `pyproject.toml` now includes explicit project license metadata.
- Done: dev build tooling path documented and enabled (`build` in dev group).
- Verified: `uv run python -m skillsmith --help` passes.
- Verified: `uv run --group dev python -m build` passes and produces sdist/wheel.
