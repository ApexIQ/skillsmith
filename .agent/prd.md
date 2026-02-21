# [.agents/prd.md] / Skill Versioning & Evolution

## 1. Overview
As the skills library Grows, projects will need a way to keep their local skills up-to-date with the latest best practices without manual copy-pasting or losing project-specific customizations.

**Success Criteria:**
- Every skill in the library has a SemVer version.
- `skills-agent update` identifies outdated skills in the current project.
- Intelligent "safe update" mechanism (warns before overwriting or preserves local notes).

## 2. Business & User Context
**User Needs:**
- Stay updated with evolving AI patterns (e.g., new prompt techniques).
- Avoid manual maintenance of the `.agents` folder.

## 3. Functional Requirements
- **FR1: Version Metadata:** Mandatory `version` field in `SKILL.md` frontmatter.
- **FR2: Update Command:** `skills-agent update [--dry-run]` to check/sync local skills with the template library.
- **FR3: Version Stability:** `skills-agent lint` enforces SemVer compliance.

## 4. Non-Functional Requirements (NFR)
- **Safety:** Never overwrite a file that has been modified since `init`/`add` without a confirmation or backup.

## 5. UX & Interaction Specs
- `skills-agent update`: Displays a diff-style summary:
    - `[UPGRADE]` skill-name: 0.1.0 -> 0.2.0
    - `[SKIPPED]` skill-name (User modified)

## 6. AI / Model Expectations
- Agents can check the version of the skill they are using to ensure compatibility with their own operating logic.

## 7. Risks & Mitigations
- **Risk:** Overwriting user customizations.
- **Mitigation:** Implement a "last-known-checksum" or simple modified-time check to detect local changes.

## 8. Success Metrics & KPIs
- Number of skills successfully updated in test projects.
- User satisfaction with the "merge" or "safe-overwrite" experience.

## 9. Dependencies
- `PyYAML` (already added).
- `hashlib` (standard lib) for change detection.

## 10. Revision History
- [2026-01-20] Proposed Versioning & Update module.

## 11. Skill Expansion (v0.2.0)
- **Library Growth:** Integrated **615+ external skills** covering diverse domains (Security, DevOps, Mobile, SaaS, etc.).
- **Normalization:** Converted all skills to `snake_case` directory structure and enforced SemVer metadata.
- **Key Additions:**
    - `ui_ux_design`: Advanced design system generation.
    - `software_architecture`: Quality-focused architectural patterns.
    - `prompt_engineering`: V0.2.0 with advanced techniques.
    - `security_audit`, `fastapi_best_practices`, `react_best_practices`, and hundreds more.

## 12. Universal Agent Platform (v0.3.0)

**Problem:** `skillsmith init` only created `AGENTS.md` and `.agent/`. Users on Gemini, Cursor, Claude, Windsurf, or Copilot got zero benefit — those tools only auto-read their own config files.

**Solution:** Auto-generate platform-specific rule files during `skillsmith init`:

| Platform | File Created | Official Format |
|---|---|---|
| Gemini CLI | `GEMINI.md` | `@file.md` imports, `/memory` commands |
| Claude Code | `CLAUDE.md` | Concise, <300 lines, progressive disclosure |
| Cursor | `.cursorrules` + `.cursor/rules/skillsmith.mdc` | Legacy + modern `.mdc` YAML frontmatter |
| Windsurf | `.windsurfrules` | XML-style grouping tags, <6000 chars |
| Copilot | `.github/copilot-instructions.md` | Actionable language, no external links |

**Key Design Decisions:**
1. **Smart Append**: If a platform file already exists, append our section using a `<!-- Skillsmith -->` marker — never overwrite.
2. **Single Source of Truth**: Skills stay in `.agent/skills/`. Platform rule files point agents to that directory.
3. **GSD State Files**: Added `PROJECT.md`, `ROADMAP.md`, `STATE.md` templates to `.agent/` for context persistence.

**Success Criteria:**
- `skillsmith init` in empty folder → all platform files + `.agent/` created.
- `skillsmith init` in existing Cursor project → `.cursorrules` appended, not replaced.
- Agent in any platform → immediately sees skills and follows GSD protocol.

## 13. Revision History
- [2026-01-20] Proposed Versioning & Update module.
- [2026-02-18] Added v0.3.0 Universal Agent Platform: platform rule files, GSD state templates, smart append logic.
- [2026-02-18] Added v0.3.1 Developer Experience & Compliance features: doctor, budget, lint, compose.
- [2026-02-18] Released v0.5.2: Universal OS compatibility, PATH detection, `python -m skillsmith` support.
- [2026-02-19] Released v0.5.3: Restored full 24MB skill library (625+ skills), fixed `init --all` truncated zip bug.

## 14. Developer Experience & Compliance (v0.3.1)

**Problem:** Developers had no way to verify their setup was working, no visibility into context token usage, and skills weren't interoperable with other agent frameworks.

**Solution:** 5 new features shipped in v0.3.1:

### `skillsmith doctor` — Environment Health Check
- Checks AGENTS.md, all 6 platform rule files, 3 GSD state files, skills directory
- Detects which AI tools are active (Gemini, Claude, Cursor, Windsurf, Copilot)
- Warns if STATE.md is stale (>24h) — prevents context rot
- `--fix` flag auto-runs `skillsmith init` to repair issues
- **Acceptance Criteria:** Runs in <1s, zero emoji (Windows-safe), actionable output

### `skillsmith budget` — Context Token Budget
- Measures token/char usage per platform file against each vendor's official limits
- Windsurf: 6,000 char limit | Claude: 1,500 tokens | Gemini: 2,000 tokens
- Shows ASCII progress bar vs 8,000 token recommended max
- **Acceptance Criteria:** Accurate estimates (±20%), no false positives

### `skillsmith lint --spec agentskills` — AgentSkills.io Compliance
- Validates against the AgentSkills.io open standard (Anthropic, adopted by Microsoft/OpenAI/Google/Cursor)
- Checks: required fields (name, description, version), description length, semver format
- Warns: missing `tags` (for discovery), missing `globs` (for file-scoped rules)
- **Acceptance Criteria:** All 23 bundled skills pass with only `globs` warnings (intentionally optional)

### `skillsmith compose <goal>` — Skill Composition Engine
- Reads all installed skills, scores each against goal keywords using overlap algorithm
- Picks top N (default 7) most relevant skills, ranked by score
- Generates numbered workflow `.md` in `.agent/workflows/<goal-slug>.md`
- **Acceptance Criteria:** Relevant skills ranked correctly, workflow file is valid markdown

### AgentSkills.io Tags on All 23 Skills
- Added `tags: [...]` to all 23 bundled SKILL.md files
- Tags enable discovery, filtering, and compose scoring
- **Acceptance Criteria:** `lint --spec agentskills` shows only `globs` warnings (no `tags` warnings)

**Success Metrics:**
- `skillsmith doctor` → instant feedback on setup health
- `skillsmith budget` → developers know their context load before hitting limits
- `skillsmith compose "build a saas mvp"` → generates 7-step workflow in <1s
- All 23 skills pass AgentSkills.io compliance (errors=0, warnings=globs only)

## 15. Advanced Agentic Patterns (v0.6.0)

**Problem:** Basic agentic loops were fragile. Multi-step reasoning and model-specific optimizations (o1, o3, MCP) were missing.

**Solution:**
1. **Search-then-GSD Protocol:** Mandated skill discovery as the first step of the agentic loop.
2. **Anthropic & OpenAI Patterns:** Orchestration, Parallelization, Critic Loops, and Reasoning optimization.
3. **Automated Cataloging:** `skillsmith rebuild` command for real-time library synchronization.
4. **Context Engineering:** Implemented "Just-in-Time" memory and compaction strategies.

## 16. Revision History
- [2026-01-20] Proposed Versioning & Update module.
- [2026-02-18] Added v0.3.0 Universal Agent Platform.
- [2026-02-18] Added v0.3.1 Developer Experience & Compliance.
- [2026-02-19] Released v0.5.3: Restored full 24MB skill library (625+ skills).
- [2026-02-21] Released v0.6.0: The Advanced Agentic Release (Anthropic/OpenAI/GSD Refinement).
