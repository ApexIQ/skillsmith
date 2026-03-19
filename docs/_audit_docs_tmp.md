# Docs/API Surface Audit

Scope: `README.md` vs `src/skillsmith/cli.py` and `src/skillsmith/commands/*`

## Checklist

- [x] README install instructions mention `pip install skillsmith` and optional MCP extra.
- [x] README documents several core CLI commands (`init`, `list`, `recommend`, `discover`, `add`, `update`, `lint`, `compose`, `doctor`, `budget`, `snapshot`, `watch`, `serve`).
- [ ] README command surface is stale/incomplete relative to the CLI.
- [ ] README packaging/run-from-source example matches the actual entrypoint.
- [ ] Library vs CLI boundary is clearly documented.

## Top Gaps

1. Missing CLI docs for currently wired commands: `align`, `sync`, `report`, `profile`, `audit`, `eval`, `rebuild`, `context-index`/`context`, `registry`, `registry-service`, `trust-service`.
2. README says `python -m skillsmith.cli --help`; the package actually exposes `python -m skillsmith` via `src/skillsmith/__main__.py`.
3. README presents the project mostly as a CLI tool, but the packaging metadata classifies it as a Python library and `src/skillsmith/__init__.py` only exports `__version__`, so the public import/API boundary is not explained.
4. Core happy-path docs are missing the currently important flow around `init --guided`, `sync`, `align`, and `audit --strict`.

## Minimal Fixes

- Add a compact "CLI surface" table in README that mirrors the real top-level commands.
- Replace the source-run example with `python -m skillsmith --help` or `skillsmith --help`.
- Add one short "Library vs CLI" paragraph stating whether the supported public API is CLI-only or whether imports are stable.
- Expand the quickstart/operator flow to include the current happy path: `init --guided` -> `recommend`/`add` -> `sync`/`align` -> `audit --strict`.
