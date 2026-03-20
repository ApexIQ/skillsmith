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
```

Then do:

```bash
skillsmith recommend
skillsmith add <skill-name>
skillsmith sync
skillsmith align
skillsmith audit --strict
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

## 4) Command Reference (Simple)

### Project Setup

- `skillsmith init`: Create the skillsmith workspace in your project.
- `skillsmith sync`: Re-scan your project and refresh generated files.
- `skillsmith align`: Re-render managed files from your saved profile.
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
- `skillsmith autonomous run`: Start the autonomous workflow loop.
- `skillsmith autonomous status`: Show the current autonomous workflow state.
- `skillsmith autonomous report`: Generate an autonomous workflow summary.
- `skillsmith eval`: Run evaluation and save metrics artifact.
- `skillsmith budget`: Show context/token budget usage.
- `skillsmith context-index build`: Build searchable project context index.
- `skillsmith context-index query "<query>"`: Search ranked project context.
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

## 6) Most Useful Help Commands

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

## 7) Library vs CLI

`skillsmith` is a Python package, but the supported public interface is the CLI.

- Stable: `skillsmith <command>` and `python -m skillsmith <command>`
- Not guaranteed stable: importing internal modules like `skillsmith.commands.*`

## 8) Development

Run from source:

```bash
PYTHONPATH=src python -m skillsmith --help
```

Build package artifacts:

```bash
uv run --group dev python -m build
```

## 9) Current Version

- Package version: `0.6.5`

## License

MIT. See `LICENSE`.
