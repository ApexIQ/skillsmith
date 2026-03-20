# Recipe: Team Onboarding (Minimal Config)

Goal: onboard a teammate quickly using profile sync and generated agent instructions.

## Commands

```bash
skillsmith init --guided
skillsmith sync
skillsmith align
skillsmith report
```

## Expected Result

- Shared project profile and context are generated in `.agent/`.
- Tool-native instruction files are rendered consistently from profile data.
- `skillsmith report` gives a quick status snapshot for handoff.

