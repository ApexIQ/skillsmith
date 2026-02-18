# skillsmith

[![PyPI version](https://img.shields.io/pypi/v/skillsmith.svg)](https://pypi.org/project/skillsmith/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`skillsmith` is a Python CLI for bootstrapping agent-ready project context.

It scaffolds a standard `.agent/` workspace, generates platform-specific instruction files (Claude, Gemini, Cursor, Windsurf, Copilot), manages local skills, and can expose installed skills through an MCP server.

## Quick Start

```bash
pip install skillsmith
skillsmith init
```

## What It Generates

Running `skillsmith init` creates:

- `AGENTS.md`
- `GEMINI.md`
- `CLAUDE.md`
- `.cursorrules`
- `.cursor/rules/skillsmith.mdc`
- `.windsurfrules`
- `.github/copilot-instructions.md`
- `.agent/` with state/templates and installed starter skills

`.agent/` includes:

- `PROJECT.md`
- `ROADMAP.md`
- `STATE.md`
- `prd.md`
- `guides/`, `plans/`, `workflows/`
- `skills/`

## Current Starter Skills

The current bundled starter pack installs three lifecycle skills by default:

- `atomic_execution`
- `context_optimization`
- `project_state_management`

These are installed under `.agent/skills/agentic_lifecycle/...`.

## CLI Commands

### Initialize

```bash
skillsmith init
skillsmith init --minimal
skillsmith init --agents-md-only
skillsmith init --all
skillsmith init --category <category>
skillsmith init --tag <tag>
```

### Discover Skills

```bash
skillsmith list
skillsmith list --list-categories
skillsmith list --category <category>
skillsmith list --tag <tag>
```

### Manage Skills

```bash
skillsmith add <skill-name>
skillsmith add <github-directory-url>
skillsmith update
skillsmith update --force
skillsmith lint
skillsmith lint --local
skillsmith lint --spec agentskills
```

### Workflow + Health

```bash
skillsmith compose "build a saas mvp"
skillsmith doctor
skillsmith doctor --fix
skillsmith budget
```

### MCP Server

Install optional MCP dependency:

```bash
pip install skillsmith[mcp]
```

Run server:

```bash
skillsmith serve
skillsmith serve --transport http --host localhost --port 47731
```

Tools exposed by MCP server:

- `list_skills`
- `get_skill(name)`
- `search_skills(query)`
- `compose_workflow(goal)`

Claude Code integration (stdio):

```bash
claude mcp add skillsmith -- skillsmith serve
```

Claude Code integration (HTTP):

```bash
claude mcp add --transport http skillsmith http://localhost:47731/mcp
```

Cursor example (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "skillsmith": {
      "command": "skillsmith",
      "args": ["serve"]
    }
  }
}
```

## Project Status

- Package version: `0.4.0`
- Core CLI + MCP entrypoint are implemented.
- Starter templates and lifecycle skills are included in the package.

## Development

```bash
# run CLI from source
PYTHONPATH=src python -m skillsmith.cli --help
```

## License

MIT. See `LICENSE`.
