# Package-management audit

Scope: packaging basics only.

## Findings
- `pyproject.toml` has the core packaging metadata in place: `name`, `version`, `description`, `readme`, `requires-python`, authors, classifiers, URLs, runtime dependencies, optional `mcp` extra, and console scripts.
- Runtime vs optional dependency separation is present. `dependencies` carries runtime packages; `project.optional-dependencies.mcp` is isolated; `dependency-groups.dev` is separate.
- Basic metadata gap: no `license` field is declared in `project`.
- Basic tooling gap: `uv run python -m build` fails because the `build` module is not available in the project environment.

## Packaging commands
- `uv run python -m build` -> fail
  - Evidence: `C:\Users\vanam\Desktop\skills-agent\.venv\Scripts\python.exe: No module named build`
- Fresh offline venv smoke install -> pass
  - Command: create temp venv, `uv pip install --offline --python .tmp_pkg_audit_env\Scripts\python.exe .`, then run `skillsmith --help`
  - Evidence: install resolved and built `skillsmith @ file:///C:/Users/vanam/Desktop/skills-agent`, then `skillsmith --help` printed the CLI usage and command list.

## Commands run
- `Get-Content pyproject.toml`
- `uv run python -m build`
- `uv pip install --help`
- `uv sync --help`
- `uv pip install --offline --python ".tmp_pkg_audit_env\\Scripts\\python.exe" .`
- `& ".tmp_pkg_audit_env\\Scripts\\skillsmith.exe" --help`

