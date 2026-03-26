# Skillsmith Rules

- Read `AGENTS.md`, `.agent/STATE.md`, and `.agent/lessons.md`.
- Read `.agent/project_profile.yaml` and `.agent/context/project-context.md`.
- Current focus: Project using skillsmith
- **Slash Commands**: This project supports specialized engineering commands. If the user invokes them, use the corresponding MCP tool:
  - `/autonomous` -> Use `autonomous_mission`
  - `/audit`, `/security`, `/performance` -> Use `audit_repository`
  - `/explain` -> Use `explain_code`
  - `/verify` -> Use `verify_readiness`
  - `/review` -> Use `review_changes`
  - `/sync` -> Use `sync_project`
- Prefer relevant skills from `.agent/skills/` over ad hoc instructions.
- Use `.agent/workflows/` for reusable runbooks like `brainstorm`, `plan-feature`, `debug-issue`, and `test-changes`.
- Trusted publisher public keys: none
- Verify build/test behavior before claiming success.
