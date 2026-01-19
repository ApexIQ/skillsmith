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
