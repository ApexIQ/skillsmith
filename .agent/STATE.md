# Current State

> **CRITICAL**: AI agents MUST read this file at the start of every session.
> Update this file after every significant step to prevent context rot.

**Last Updated:** 2026-03-25

## Current Objective
Keep project instructions, rules, and workflows aligned with `.agent/project_profile.yaml`.

## Context
- Idea: Project using skillsmith
- Stage: existing
- Frameworks: click, pytest
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
- Moved from mock reflection to **functional Log Reflection (L2)**: `evolve reflect` now distills real binary logs from `raw_events.jsonl`.
- Implemented **Eval-to-Evolve Bridge**: Evaluation regressions trigger `EvolutionEngine` repair packets via `--auto-evolve`.
- Integrated **Self-Correction Loop**: The `EvolutionEngine` is now wired into the `autonomy` loop for "Active Repair" of degraded skills.
- Verified end-to-end memory loop: Work -> Log -> Reflect -> Lesson.

## Next Steps
1.  **Refine Heuristics**: Move the evolution logic (FIX/DERIVE) from hardcoded templates to LLM-synthesis.
2.  **Registry Sync**: Implement Team Marketplace/Registry sync for shared skill evolution.
3.  **Global Integration**: Automate `log_event` (L1) across all `skillsmith` commands.

## Known Issues
- `evolve reflect` currently uses heuristic-based categorization; needs transition to `litellm` for deep semantic distillation.
