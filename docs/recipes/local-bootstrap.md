# Recipe: Local Project Bootstrap

Goal: bootstrap a local repository into an agent-ready project with minimal manual setup.

## Commands

```bash
skillsmith start
skillsmith report --artifact-dir .agent/reports/readiness
```

## Expected Result

- `AGENTS.md` exists.
- `.agent/project_profile.yaml` and `.agent/context/project-context.md` exist.
- `skillsmith start` completes the default readiness path.
- `skillsmith report --artifact-dir` writes `report.json`, `readiness_pr.md`, and `scorecard.json`.
