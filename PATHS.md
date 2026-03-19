# Path Compatibility Matrix

## Purpose

This document defines which project paths are actually recognized by major AI coding tools and which paths are only internal `skillsmith` conventions.

Use this file when:
- designing `skillsmith init`
- deciding where generated files should live
- auditing whether an agent will automatically read a file

## Path Categories

### 1. Native Paths
Paths officially recognized by a specific tool.

### 2. Portable Paths
Paths recognized by multiple tools.

### 3. Internal Paths
Paths used by `skillsmith` internally. These are not guaranteed to be auto-read by external tools.

## Tool Matrix

| Tool | Native Project Paths | Notes |
|---|---|---|
| Codex | `AGENTS.md` | Strong cross-tool base path. |
| Claude Code | `CLAUDE.md`, `.claude/agents/`, `.claude/commands/` | Claude-specific paths should be generated explicitly. |
| Windsurf | `AGENTS.md`, `.windsurf/rules/` | Also supports nested `AGENTS.md`. |
| Cursor | `AGENTS.md`, `.cursor/rules/`, legacy `.cursorrules` | Prefer `.cursor/rules/`. |
| Zencoder | `.zencoder/rules/` | Can be configured to read other rule folders too. |
| Augment | `AGENTS.md`, `CLAUDE.md`, workspace rules | Hierarchical repo loading matters. |
| Gemini / Firebase Studio | `GEMINI.md`, `.idx/airules.md` | Firebase docs also reference `AGENTS.md` precedence in some contexts. |
| Antigravity | `.agent/rules/`, `.agent/workflows/` | This is the main case where `.agent/workflows/` is tool-aligned. |

## Recommended `skillsmith` Output Layout

### Portable Core
Generate these in all supported repos:
- `AGENTS.md`
- `.agent/project_profile.yaml`
- `.agent/PROJECT.md`
- `.agent/ROADMAP.md`
- `.agent/STATE.md`

### Claude Code
Generate:
- `CLAUDE.md`
- `.claude/agents/`
- `.claude/commands/`

Recommended default subagents:
- `planner.md`
- `researcher.md`
- `implementer.md`
- `reviewer.md`

### Cursor
Generate:
- `.cursor/rules/skillsmith.mdc`

### Windsurf
Generate:
- `.windsurf/rules/skillsmith.md`

### Zencoder
Generate:
- `.zencoder/rules/skillsmith.md`

### Gemini
Generate:
- `GEMINI.md`

### Antigravity
Generate:
- `.agent/rules/`
- `.agent/workflows/`

## Current `skillsmith` Reality

### Correct Today
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.cursor/rules/skillsmith.mdc`
- `.cursorrules`
- `.windsurfrules`
- `.agent/workflows/` as an internal convention
- `skillsmith audit` / `skillsmith doctor` are the audit surfaces for path drift, policy gates, and lockfile verification metadata
- `--strict` is the CI-oriented mode; JSON-friendly output should be treated as machine-facing when integrating these checks

### Not Yet Fully Aligned
- no `.claude/agents/`
- no `.claude/commands/`
- no `.windsurf/rules/`
- no `.zencoder/rules/`
- no explicit `.agent/rules/` output for Antigravity

## Rules For Future Features

1. Do not assume `.agent/*` is automatically understood by all tools.
2. Treat `AGENTS.md` as the best portable root instruction file.
3. Generate tool-native paths when a tool has a documented path model.
4. Keep `.agent/` as `skillsmith`'s internal source of truth, not the only delivery layer.
5. Render tool-specific files from a shared project profile.
6. Keep recommendation output explainable so users can preview why a skill or pack was selected before install.
7. Treat `skillsmith sync` as the maintenance loop for refreshing inferred repo signals and regenerated outputs.
8. Keep policy-gated install decisions and lockfile verification metadata attached to the generated outputs they validate, not to `.agent/` paths alone.

## Priority Fixes

### Priority 1
- add `.claude/agents/`
- add `.claude/commands/`
- add `.windsurf/rules/`
- add `.zencoder/rules/`

### Priority 2
- add `.agent/rules/` for Antigravity alignment
- define a single rendering pipeline for all tool outputs

### Priority 3
- add path validation in `skillsmith doctor`
- add per-tool path generation tests
- add recommendation preview/report output for install decisions
