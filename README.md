# skillsmith Documentation

[![PyPI version](https://img.shields.io/pypi/v/skillsmith.svg)](https://pypi.org/project/skillsmith/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`skillsmith` helps you prepare a project so AI coding tools can understand your project better and work more reliably.

This guide is written for beginners. You can copy and run commands as shown.

## 1) Install

```bash
pip install skillsmith
```

Optional MCP support:

```bash
pip install "skillsmith[mcp]"
```

If `skillsmith` is not found, use module mode:

```bash
python -m skillsmith --help
```

## 2) 60-Second Start

Run this inside your project folder:

```bash
skillsmith init --guided
skillsmith doctor
skillsmith compose "build a project summary"
```

## 3) What You Get

After setup, skillsmith creates and manages:

- `.agent/` project context and memory files
- AI-tool instruction files (for supported tools)
- skill installation and tracking (`skills.lock.json`)
- workflow/evaluation/trust utilities

### Context Tiers

skillsmith keeps context in simple layers:

- Tier 1: the active task and recent instructions
- Tier 2: project state in `.agent/project_profile.yaml` and `.agent/context/project-context.md`
- Tier 3: retrieval and memory artifacts in `.agent/context/index.json`, `.agent/context/query_policy.json`, and `.agent/snapshots/`

`skillsmith context-index build` writes the retrieval index, `skillsmith context-index query` returns ranked matches with score breakdowns, and `skillsmith snapshot` saves or restores the `.agent/` folder.
Snapshot notes, when provided, are stored beside the archive in `.agent/snapshots/` as `.note.txt` files and are the place to keep short memory lessons or handoff notes.

- `skillsmith context-index recover`: Restore the last known-good context index state after drift, cache problems, or a bad rebuild.
- `skillsmith context-index refresh-changed`: Rebuild context data for files that changed since the last index update.

### Recall Cache

`skillsmith` can reuse recent retrieval results from `.agent/context/recall_cache.json` to make repeated `context-index query` and `compose` runs cheaper and faster.

- Default TTL: 900 seconds.
- Invalidation: cache entries are dropped when the query, tier/depth/limit, context index fingerprint, or query policy fingerprint changes.
- Recovery: if the cache looks stale or wrong, remove it and rebuild the index.
- If the index itself may be stale, run `skillsmith context-index recover` first; if only changed files need to be reprocessed, use `skillsmith context-index refresh-changed`.

Troubleshooting commands:

```bash
rm .agent/context/recall_cache.json
skillsmith context-index build
skillsmith context-index recover
skillsmith context-index refresh-changed
skillsmith context-index query "<query>"
skillsmith compose "<goal>"
```

## 4) Command Reference (Simple)

### Project Setup

- `skillsmith init`: Create the skillsmith workspace in your project.
- `skillsmith sync`: Re-scan your project and refresh generated files.
- `skillsmith align`: Re-render managed files from your saved profile.
- `skillsmith suggest`: Recommend the next 1-3 high-leverage commands based on current project state.
- `skillsmith doctor`: Health check for setup and environment.
- `skillsmith audit`: Full quality/trust/drift audit.
- `skillsmith report`: Human-readable project status summary.
- `skillsmith profile`: View or change project profile settings.

### Skills

- `skillsmith list`: Show available skills.
- `skillsmith discover <query>`: Search for skills by keyword.
- `skillsmith recommend`: Suggest skills based on your project.
- `skillsmith add <skill-name-or-url>`: Install one skill.
- `skillsmith update`: Update installed local skills.
- `skillsmith lint`: Validate skill metadata and structure.
- `skillsmith rebuild`: Rebuild local catalog from skill files.
- `skillsmith assets status`: Show optional runtime asset availability.
- `skillsmith assets bootstrap`: Download/copy runtime assets into local cache.

### Workflow and Evaluation

- `skillsmith compose "<goal>"`: Generate a step-by-step workflow for a goal.
- `skillsmith safety ...`: Manage local safety modes (`status`, `careful`, `freeze`, `guard`, `unfreeze`).
- `skillsmith autonomous run`: Start the autonomous workflow loop.
- `skillsmith autonomous status`: Show the current autonomous workflow state.
- `skillsmith autonomous report`: Generate an autonomous workflow summary.
- `skillsmith eval`: Run evaluation and save metrics artifact.
- `skillsmith budget`: Show context/token budget usage.
- `skillsmith context-index build`: Build searchable project context index.
- `skillsmith context-index query "<query>"`: Search ranked project context.
- `skillsmith context-index recover`: Restore the last known-good context index state.
- `skillsmith context-index refresh-changed`: Refresh context entries for changed files.
- `skillsmith context ...`: Alias for `context-index`.

### Autonomous Contract

The 8-pillar autonomy contract in this release is:

1. Bounded domain: autonomous runs currently support recommendation workflows only.
2. Benchmark-driven: runs load a benchmark pack from `.agent/autonomy/benchmarks/`.
3. Preflight safety: runs stop early if git is missing, the repo is not clean, or preflight fails.
4. Bounded execution: `--max-hours`, `--max-iterations`, and `--early-stop-fails` cap loop length.
5. Score gating: `--score-gate` and `--strict-gate` control keep/discard/crash behavior.
6. Session persistence: each run writes session JSON, state JSON, and a latest pointer.
7. Audit trail: `results.tsv` records preflight, iteration, and summary rows for each session.
8. Status/report access: `status` and `report` resolve the latest session from `.agent/autonomy/latest.json`.

Artifacts and paths:

- `.agent/autonomy/runs/<session-id>/session.json`
- `.agent/autonomy/runs/<session-id>/state.json`
- `.agent/autonomy/runs/<session-id>/iterations/`
- `.agent/autonomy/latest.json`
- `.agent/autonomy/results.tsv`
- `.agent/autonomy/benchmarks/`

Safety behavior:

- Dirty git trees are blocked before execution starts.
- Strict gate failures end the run with a crash result.
- Missing or invalid latest-session data falls back to "no autonomy session found" instead of raising.

### Registry and Trust (Advanced / Team Use)

- `skillsmith registry`: Manage team registry entries/lifecycle.
- `skillsmith registry-service`: Run/sync local registry service API.
- `skillsmith trust-service`: Run/sync local trust service API.

### MCP Server and Context Snapshots

- `skillsmith serve`: Start MCP server for tool integrations.
- `skillsmith snapshot`: Save/restore `.agent` context snapshots.
- `skillsmith watch`: Monitor context drift and staleness.

### Maintenance

- `skillsmith update`: Update installed skills.

## 5) Beginner-Friendly Workflows

### A) First time in a project

```bash
skillsmith init --guided
skillsmith recommend
skillsmith add <skill-name>
skillsmith audit
```

### B) Before starting a new task

```bash
skillsmith sync
skillsmith align
skillsmith compose "build <your-goal>"
```

### C) Before merge/release

```bash
skillsmith eval
skillsmith audit --strict
skillsmith report
```

### Production Recipes

- Local bootstrap: [docs/recipes/local-bootstrap.md](docs/recipes/local-bootstrap.md)
- CI gate flow (`doctor` + `eval`): [docs/recipes/ci-gate-flow.md](docs/recipes/ci-gate-flow.md)
- Team onboarding (minimal config): [docs/recipes/team-onboarding.md](docs/recipes/team-onboarding.md)

## 6) Failure Recovery

Use these exact commands for common failures:

1. `skillsmith` command is not found
   Run:
   ```bash
   python -m skillsmith --help
   ```
2. Core generated files are missing or drifted
   Run:
   ```bash
   skillsmith sync
   skillsmith align
   skillsmith doctor
   ```
3. Context retrieval feels stale or inconsistent
   Run:
   ```bash
   rm .agent/context/recall_cache.json
   skillsmith context-index recover
   skillsmith context-index refresh-changed
   skillsmith context-index query "project context"
   ```
4. Lockfile/integrity checks fail in CI
   Run:
   ```bash
   skillsmith doctor --strict
   skillsmith audit --strict
   ```
5. Workflow output does not match current project state
   Run:
   ```bash
   skillsmith sync
   skillsmith compose "build a project summary"
   ```
6. Optional runtime assets are missing
   Run:
   ```bash
   skillsmith assets status
   skillsmith assets bootstrap
   ```

## 7) Most Useful Help Commands

Show global help:

```bash
skillsmith --help
```

Show help for one command:

```bash
skillsmith <command> --help
```

Examples:

```bash
skillsmith init --help
skillsmith audit --help
skillsmith registry-service --help
```

## 8) Library vs CLI

`skillsmith` is a Python package, but the supported public interface is the CLI.

- Stable: `skillsmith <command>` and `python -m skillsmith <command>`
- Not guaranteed stable: importing internal modules like `skillsmith.commands.*`

### Python SDK (Public API)

Import this stable, import-first surface when embedding `skillsmith` in another Python tool:

```python
from skillsmith import init_project, compose_workflow, doctor_summary

project = init_project(".")
workflow = compose_workflow("build a project summary")
health = doctor_summary(".")
```

This is the stable import-first surface for embedding. Use these entry points instead of reaching into internal modules.

### Stability and Deprecation Policy (v0.x)

- Stable contract in v0.x:
  - Top-level CLI commands wired in `skillsmith.cli:main`
  - Python SDK entry points: `init_project`, `compose_workflow`, `doctor_summary`
- Experimental surface:
  - Internal modules under `skillsmith.commands.*`
  - Internal helper functions not re-exported from `skillsmith.__init__`
- Deprecations:
  - Deprecated options keep working for at least one minor release with an explicit warning.
  - Migration path is documented in command help/README when a deprecation is introduced.

## 9) Development

Run from source:

```bash
PYTHONPATH=src python -m skillsmith --help
```

Build package artifacts:

```bash
uv run --group dev python -m build
```

## 10) Current Version

- Package version: `0.6.5`

## License

MIT. See `LICENSE`.
