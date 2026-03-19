# skillsmith Feature Guide

## Purpose

This document captures:
- current features in `skillsmith`
- required changes to make the product stronger
- recommended features for the next product iterations

It is intended to be a practical reference for implementation, review, and roadmap planning.

## Current Features

### 1. Project Scaffolding
- `skillsmith init` creates:
  - `AGENTS.md`
  - `.agent/PROJECT.md`
  - `.agent/ROADMAP.md`
  - `.agent/STATE.md`
  - platform instruction files for Claude, Gemini, Cursor, Windsurf, and Copilot
- supports:
  - `--minimal`
  - `--agents-md-only`
  - `--all`
  - `--category`
  - `--tag`

### 2. Skill Management
- `skillsmith list` lists available skills from the catalog
- `skillsmith add <skill-name>` installs a local skill into `.agent/skills/`
- `skillsmith add <github-url>` downloads a remote skill directory from GitHub
- `skillsmith update` updates installed skills from local templates
- `skillsmith rebuild` rebuilds the skill catalog from a skill directory
- `skillsmith sync` re-infers repo signals, refreshes the saved profile, and re-renders managed outputs

### 3. Validation and Health
- `skillsmith lint` validates local skills
- `skillsmith doctor` checks missing setup files, repo health, and lockfile integrity
- `skillsmith doctor --strict` exits non-zero on warnings or errors for CI gating
- `skillsmith audit` provides the operator-facing audit view with policy and verification details
- `skillsmith budget` estimates prompt/context size
- `skillsmith watch` detects branch changes, stale state, and skill changes
- `skillsmith snapshot` saves and restores `.agent/` snapshots

### 4. Workflow and MCP
- `skillsmith compose` generates a workflow from relevant skills
- `skillsmith serve` exposes local skills through MCP
- MCP tools currently support:
  - `list_skills`
  - `get_skill`
  - `search_skills`
  - `compose_workflow`

### 5. Recommendation Visibility
- `skillsmith discover` shows ranked candidates with a `Why` column
- guided install and `sync --auto-install` print concise recommendation reasons
- `skills.lock.json` stores recommendation rationale for installed skills
- curated starter packs bias recommendations toward the repo shape instead of generic matches
- provider installs are gated by `trusted_skill_sources` and `min_remote_trust_score`
- audit/report output can be rendered for humans or machine consumption

## Current Product Gaps

These are the biggest gaps between the current implementation and the target product direction.

### 1. No Guided Setup
- setup is template-first, not interview-first
- the user must already know which flags, skills, and categories to use

### 2. No Unified Project Profile
- generated files are copied independently
- `AGENTS.md`, platform files, and `.agent/*.md` are not rendered from one shared source of truth

### 3. No Claude Subagent Generation
- the project does not yet generate `.claude/agents/`
- there is no built-in multi-agent workflow pack for Claude Code

### 3b. Tool Path Alignment Is Incomplete
- `skillsmith` currently mixes internal paths and tool-native paths
- `.agent/` is used as if all tools understand it automatically, which is not true
- path generation is not yet mapped per tool such as Claude, Zencoder, Windsurf, Cursor, Gemini, and Antigravity

### 4. Limited Workflow Quality
- workflow composition is keyword-based and shallow
- no stage-aware workflows such as planning, implementation, testing, review, release

### 5. Weak External Skill Discovery
- GitHub directory download exists, but there is no trust-ranked registry discovery
- no lockfile, provenance tracking, or compatibility scoring
- recommendation selection is still not exposed as a dedicated preview/report command

### 6. Incomplete Test Coverage
- there is some command-focused test work, but command behavior still needs stronger verification
- no solid coverage for guided flows, alignment behavior, or external provider logic

## Required Changes

These changes should be treated as required for the next major improvement cycle.

### 1. Add `init --guided`
The CLI should ask:
- what the user is building
- current project stage
- target stack
- deployment target
- priorities such as speed, security, maintainability
- whether remote skills should be allowed

Output should include:
- `.agent/project_profile.yaml`
- aligned generated rule files
- recommended default skills

### 2. Add a Single Source of Truth
Implement a shared project profile model that drives:
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- Cursor and Windsurf files
- `.agent/PROJECT.md`
- `.agent/ROADMAP.md`
- `.agent/STATE.md`

### 3. Generate 4 Default Claude Subagents
The default scaffold should generate:
- `.claude/agents/planner.md`
- `.claude/agents/researcher.md`
- `.claude/agents/implementer.md`
- `.claude/agents/reviewer.md`

Each subagent should have:
- clear responsibility
- handoff rules
- verification requirements
- links back to `.agent/STATE.md` and project profile

### 3b. Generate Tool-Native Paths
`skillsmith init` should generate the correct documented paths per tool.

Required outputs:
- `AGENTS.md` for portable tool support
- `CLAUDE.md`, `.claude/agents/`, `.claude/commands/`
- `.cursor/rules/skillsmith.mdc`
- `.windsurf/rules/skillsmith.md`
- `.zencoder/rules/skillsmith.md`
- `GEMINI.md`
- `.agent/rules/`, `.agent/workflows/` for Antigravity

### 4. Add Workflow Packs
Ship reusable workflows such as:
- `discover-project`
- `plan-feature`
- `implement-feature`
- `debug-issue`
- `review-pr`
- `ship-release`

These should be generated or selected based on the project profile.
They should also follow a clear artifact model:
- rules = behavior
- skills = procedural knowledge
- workflows = manually invoked runbooks
- agents = specialist workers

### 5. Improve Skill Discovery
Add a provider layer for:
- local bundled skills
- GitHub-based skill sources
- `skills.sh`
- MCP-backed sources

This layer should support:
- search
- fetch
- metadata normalization
- source attribution
- compatibility checks
- trust and freshness scoring

### 6. Add Generated Project Context
Add a machine-maintained project context artifact inspired by tools like Zencoder.

Recommended output:
- `.agent/context/project-context.md`

This file should capture:
- detected stack
- build/test commands
- package manager
- repo layout
- architecture notes
- important conventions

### 7. Strengthen Tests
Required test areas:
- `init` with default and guided modes
- generated file alignment
- subagent generation
- provider ranking and filtering
- MCP command behavior
- update safety and local modification handling

## Recommended Changes

These are strongly recommended after the required work is stable.

### 1. Add `skills.lock.json`
Track:
- installed skills
- source
- version
- checksum
- trust score
- compatibility notes

### 2. Add `skillsmith align`
This command should re-render all generated project files from the saved profile.

### 3. Add Drift Detection
Detect when:
- repo stack changes
- platform files drift from the project profile
- skills are stale or no longer relevant

### 3b. Add Recommendation Preview / Report
Add a dedicated command that previews the selected starter packs and remote candidates before install.
It should show:
- the curated pack used
- source and trust score
- repo-fit reasons
- installability and provenance

### 4. Add Trust and Provenance Rules
Remote skills should include:
- author
- source
- version
- last updated
- license
- trust level
- verification metadata such as checksum and install-path provenance

### 5. Add Better Workflow Composition
Move from simple keyword scoring to:
- project-type matching
- stack matching
- stage-aware workflow selection
- quality-priority aware recommendations

### 6. Add Team Modes
Support generation modes such as:
- startup-speed
- enterprise-safety
- solo-builder
- product-engineering

Each mode should adjust:
- rule strictness
- workflow defaults
- recommended skills

### 8. Add Path Validation
`skillsmith doctor` should validate:
- missing tool-native paths
- legacy paths that should be migrated
- mismatches between generated files and configured target tools
- policy-gated installs and lockfile verification metadata

## Recommended Feature Priority

### Priority 1
- `init --guided`
- `project_profile.yaml`
- aligned rendering
- 4 Claude subagents

### Priority 2
- workflow packs
- `skills.sh` and registry discovery
- improved tests
- recommendation preview/report command

### Priority 3
- lockfile
- drift detection
- trust scoring
- advanced workflow ranking

## Acceptance Criteria For the Next Milestone

The next milestone should be considered complete when:
- a new user can run one guided command and get a usable setup
- all generated instruction files are aligned from one source of truth
- Claude Code subagents are created automatically
- tool-native directories are generated for the selected tools
- the default setup includes a clear workflow path to get work done
- recommendation choices can be previewed with explanation before install
- remote skill discovery is designed behind a provider abstraction
- tests cover the main command behaviors and generation logic
