# Project Context

## Summary
- Idea: Project using skillsmith
- Stage: existing
- App type: library
- Package manager: uv
- Deployment target: github-actions

## Languages
- python

## Frameworks
- click
- pytest

## Commands
- Build: uv build
- Test: pytest, python -m unittest

## Priorities
- testability
- maintainability
- verification
- automation

## Target Tools
- antigravity
- claude
- codex
- copilot
- cursor
- gemini
- windsurf

## Skill Policy
- Allow remote skills: false
- Trusted sources: local
- Allowed remote domains: github.com, skills.sh
- Blocked sources: none
- Require pinned GitHub refs: true
- Trusted publisher keys: none
- Trusted publisher public keys: none
- Publisher verification mode: optional
- Publisher signature scheme mode: auto
- Allowed publisher signature algorithms: hmac-sha256, rsa-sha256
- Publisher key rotation: none
- Minimum remote trust: 65
- Minimum remote freshness: 0
- Required remote licenses: none

## Top-Level Files
- .agent
- .claude
- .cursor
- .github
- .windsurfrules
- AGENTS.md
- CLAUDE.md
- GEMINI.md
- README.md
- ROADMAP.md
- UPCOMING_FEATURES.md
- pyproject.toml
- src
- tests
- uv.lock
