# Roadmap: skillsmith

## Phase 1: Guided Onboarding
- Add `skillsmith init --guided` to interview the user about idea, app type, stack, deployment, team preferences, quality bar, and constraints.
- Infer defaults from the repo before prompting.
- Save the result as `.agent/project_profile.yaml`.

## Phase 2: Alignment Engine
- Generate all rule files and `.agent/*.md` from the same profile.
- Add `skillsmith align` to re-render aligned files when the profile changes.
- Stop duplicating logic across `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Cursor, Windsurf, and Copilot instructions.

## Phase 3: Registry Federation
- Add a provider abstraction for local templates, `skills.sh`, curated registries, and MCP-backed discovery.
- Score skills by relevance, trust, freshness, popularity, and compatibility.
- Add lockfiles so teams can reproduce the exact skill set.

## Phase 4: Workflow Composer
- Replace simple keyword composition with profile-aware workflow generation.
- Generate workflows by project stage: discovery, implementation, debugging, review, release.
- Add parameterized workflow templates and acceptance criteria.

## Phase 5: Continuous Adaptation
- Add `skillsmith doctor --fix`, `watch`, and recommendation loops that suggest missing skills when the stack changes.
- Support branch-specific state, roadmap drift detection, and skill update suggestions.

## Phase 6: Ecosystem Quality
- Add stronger validation, provenance tracking, and security policy enforcement for remote skills.
- Publish a stable schema for project profiles, registry records, and workflow bundles.
