# Recipe: Local Project Bootstrap

Goal: bootstrap a local repository into an agent-ready project with minimal manual setup.

## Commands

```bash
skillsmith init --guided
skillsmith doctor
skillsmith compose "build a project summary"
```

## Expected Result

- `AGENTS.md` exists.
- `.agent/project_profile.yaml` and `.agent/context/project-context.md` exist.
- `skillsmith doctor` reports a healthy setup.
- `skillsmith compose` prints a generated workflow.

