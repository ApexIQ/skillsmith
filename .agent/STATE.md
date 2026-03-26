# Current State

> **CRITICAL**: AI agents MUST read this file at the start of every session.
> Update this file after every significant step to prevent context rot.

**Last Updated:** 2026-03-26

## Current Objective
Keep project instructions, rules, and workflows aligned with `.agent/project_profile.yaml`.

## Context
- Idea: Project using skillsmith
- Stage: existing
- Frameworks: click, pytest, arch-business-logic, arch-ui, arch-unknown
- Target tools: antigravity, claude, codex, copilot, cursor, gemini, windsurf
- Trusted skill sources: local
- Allowed remote domains: github.com, skills.sh
- Require pinned GitHub refs: true
- Trusted publisher keys: none
- Trusted publisher public keys: none
- Publisher verification mode: optional
- Publisher signature scheme mode: auto
- Allowed publisher signature algorithms: hmac-sha256, rsa-sha256
- Publisher key rotation: none
- Minimum remote trust: 65

## Recent Changes
- Integrated **Arize Phoenix** for local, persistent mission observability.
- Implemented **Mission Auditor** (`skillsmith audit`) for trace reflection and self-correction.
- Configured persistent OTel database storage in `.phoenix/`.
- Updated agent standards (`AGENTS.md`, `GEMINI.md`) to mandate mission auditing.

## Next Steps
1. Enhance the Auditor to provide specific remediation hints for failed spans.
2. Implement performance benchmarking using the now-persistent trace database.
3. Stabilize the `evolve` command to use the local trace history for better reflection.

## Known Issues
- `DependencyConflict`: `openai >= 1.69.0` missing in some environments (non-blocking for observability).
