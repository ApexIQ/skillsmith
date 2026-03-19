# Project Overview

## Vision
Build `skillsmith` into the default project-orchestration layer for coding agents: a guided system that understands the user’s product idea, stack, constraints, and workflow, then assembles the right rules, skills, MCP integrations, and execution plan automatically.

## Tech Stack
- Language: Python 3.9+
- CLI: Click + Rich
- Content format: Markdown + YAML frontmatter + JSON catalogs
- Discovery: local templates, `skills.sh`, MCP-compatible registries, curated catalogs
- Transport: stdio/HTTP MCP

## Architecture
`skillsmith` should evolve from a static scaffold generator into a four-layer system:

1. Interview and inference layer
Collect project intent from the user and infer stack/context from the repo.

2. Registry and trust layer
Search local and remote skill sources, normalize metadata, rank candidates, and apply trust/safety rules.

3. Composition layer
Generate aligned `AGENTS.md`, platform rules, `.agent/PROJECT.md`, `.agent/ROADMAP.md`, `.agent/STATE.md`, and task workflows from a shared project profile.

4. Runtime delivery layer
Expose selected skills and workflows through CLI commands and MCP so agents can fetch only what they need.

## Product Principles
1. Guided first-run over blank scaffolding.
2. Generic inputs, opinionated outputs.
3. One source of truth for project context.
4. Dynamic skill discovery over static bundling.
5. Trust-ranked external skills, not blind installation.
6. Reproducible workflows that survive model/tool changes.
