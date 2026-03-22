# Skillsmith Latest Version CLI Validation Issues

Date: 2026-03-22  
Test environment: `C:\Users\vanam\Desktop\skillsmith-latest-e2e-20260322`  
Installed version: `skillsmith==0.6.8`

## Coverage Executed
- Full CLI command-surface traversal with `--help` on every discovered command/subcommand path: `67` paths, `0` help failures.
- Runtime smoke execution on key non-interactive commands: `13` commands, `12` passed, `1` non-zero.

## Issues Found

### 1) Missing Version Flag on Root CLI
- Severity: Medium
- Status: Resolved in source
- Command:
```powershell
uv run skillsmith --version
```
- Actual:
```text
Error: No such option: --version
```
- Expected:
`skillsmith --version` should print the installed package version and exit `0`.
- Impact:
Breaks standard CLI ergonomics and automated version checks that rely on root `--version`.
- Resolution:
Added root CLI version option in `src/skillsmith/cli.py` using Click `version_option`, backed by `skillsmith.__version__`.

### 2) `context-index freshness` Fails in Fresh Minimal Init Without Lockfile
- Severity: Low
- Status: Resolved in source
- Command:
```powershell
uv run skillsmith context-index freshness --json
```
- Actual:
Exits `1` in a freshly initialized minimal project because `skills.lock.json` is missing.
- Expected:
Either:
- Exit `0` with warning-only status in minimal bootstraps, or
- Keep exit `1` but clearly document this strict requirement in command help text.
- Impact:
Can look like a command failure for first-time users before any install/sync actions.
- Resolution:
Updated freshness evaluation so missing `skills.lock.json` is treated as optional/non-blocking for overall freshness `ok`, while still reported in checks with remediation.

## Artifacts
- `C:\Users\vanam\Desktop\skillsmith-latest-e2e-20260322\command_test_results.json`
- `C:\Users\vanam\Desktop\skillsmith-latest-e2e-20260322\runtime_smoke_results.json`

## Verification
- `uv run python -m unittest tests.test_cli_version tests.test_context_index_freshness -v` -> all passed.
