# Recipe: Team Onboarding (Minimal Config)

Goal: onboard a teammate quickly using profile sync and generated agent instructions.

## Commands

```bash
skillsmith start
skillsmith report --artifact-dir .agent/reports/readiness
skillsmith sync
skillsmith align
```

## Expected Result

- Shared project profile and context are generated in `.agent/`.
- Readiness artifacts are emitted for CI/PR handoff.
- Tool-native instruction files are rendered consistently from profile data.
- `skillsmith report` gives a quick status snapshot for handoff.
