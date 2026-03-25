# Workflow: bootstrap

- **Goal**: bootstrap a new module or service for library click, pytest
- **Idea**: Project using skillsmith
- **Stage**: existing
- **App type**: library
- **Frameworks**: click, pytest
- **Priorities**: testability, maintainability, verification, automation
- **Skills**: test_repair_skill

## Stages

### Discover
> Read .agent/project_profile.yaml and .agent/context/project-context.md before taking action.

**Objectives**:
- Read .agent/project_profile.yaml and .agent/context/project-context.md before taking action.
- Confirm the project stage, app type, frameworks, and priorities for goal: bootstrap a new module or service for library click, pytest.
- Top relevant skills: test_repair_skill.

**Acceptance Checks**:
- [ ] Project profile and generated context are present or inferred without error.
- [ ] The ranked skill list is deterministic for the current goal and profile.
- [ ] Target tools and project shape are visible in the workflow output.

**Evidence**:
- .agent/project_profile.yaml
- .agent/context/project-context.md
- .agent/context/index.json

### Plan
> Turn the goal into a minimal patch plan with explicit verification checkpoints.

**Objectives**:
- Turn the goal into a minimal patch plan with explicit verification checkpoints.
- Name the touched files or subsystems before any edit is made.
- Record the chosen execution mode and retry budget for the run.

**Acceptance Checks**:
- [ ] The plan names concrete files, commands, or subsystems.
- [ ] Every planned step has at least one verification check.
- [ ] Planner-editor mode, when selected, is reflected in the workflow text.

**Evidence**:
- selected skill names
- execution mode
- reflection retry budget

### Build
> Implement the smallest coherent change needed for the goal.

**Objectives**:
- Implement the smallest coherent change needed for the goal.
- Keep edits scoped to the selected files and avoid unrelated refactors.
- For debug goals, reproduce the issue and capture the failing behavior.
- For brainstorm goals, compare the candidate approaches and choose the recommended path.

**Acceptance Checks**:
- [ ] The patch changes only the files needed for the requested goal.
- [ ] The requested behavior is present in the generated workflow output.
- [ ] The implementation preserves the current command surface and backward compatibility.

**Evidence**:
- edited files
- goal-specific behavior
- workflow steps list

### Review
> Inspect the changed files for correctness, regressions, and missing coverage.

**Objectives**:
- Inspect the changed files for correctness, regressions, and missing coverage.
- Summarize findings first when risks remain, then note any verification gaps.
- Validate that the workflow still reads cleanly as a handoff artifact.

**Acceptance Checks**:
- [ ] The review names concrete risks or confirms the change is safe.
- [ ] The review output is ordered and actionable for the next agent.
- [ ] No unrelated files or behaviors are introduced into the plan.

**Evidence**:
- changed files
- risk notes
- review summary

### Test
> Run the relevant automated tests for the changed workflow behavior.

**Objectives**:
- Run the relevant automated tests for the changed workflow behavior.
- Capture the exact command output or assertion evidence for the change.
- Prefer the smallest test surface that still proves the new stage structure.

**Acceptance Checks**:
- [ ] Targeted tests pass after the implementation change.
- [ ] The failure mode is observable if the stage structure regresses.
- [ ] The test suite still covers the existing `steps` list contract.

**Evidence**:
- test command output
- passing assertions
- existing compose compatibility

### Ship
> Make the workflow output usable as a release-grade handoff artifact.

**Objectives**:
- Make the workflow output usable as a release-grade handoff artifact.
- Keep the command output deterministic for CLI and file-based use.
- Preserve the current release notes, rollback, and packaging signals.

**Acceptance Checks**:
- [ ] The generated workflow includes both stage structure and the legacy `steps` list.
- [ ] Compose output remains stable across repeated runs with the same inputs.
- [ ] The result can be written to a file without additional cleanup.

**Evidence**:
- workflow YAML output
- output file path
- deterministic render

### Reflect
> Summarize what the evidence says about the current run.

**Objectives**:
- Summarize what the evidence says about the current run.
- Carry forward the retry budget and feedback signals only when they exist.
- Use the observed results to inform the next iteration instead of guessing.

**Acceptance Checks**:
- [ ] Reflection text is grounded in the run's actual feedback or retry state.
- [ ] Any mode suggestion comes from the current evidence, not a dummy rule.
- [ ] The workflow keeps the same structure if no feedback is available.

**Evidence**:
- feedback artifact
- reflection retry count
- mode suggestion state

## Steps Summary
1. Read .agent/project_profile.yaml and .agent/context/project-context.md.
2. Confirm the requested goal against the current project stage and target tools.
3. [AND] Discover stage: Read .agent/project_profile.yaml and .agent/context/project-context.md before taking action. Acceptance: Project profile and generated context are present or inferred without error.; The ranked skill list is deterministic for the current goal and profile..
4. [OR] Plan stage: Turn the goal into a minimal patch plan with explicit verification checkpoints. Acceptance: The plan names concrete files, commands, or subsystems.; Every planned step has at least one verification check..
5. [OR] Build stage: Implement the smallest coherent change needed for the goal. Acceptance: The patch changes only the files needed for the requested goal.; The requested behavior is present in the generated workflow output..
6. [AND] Review stage: Inspect the changed files for correctness, regressions, and missing coverage. Acceptance: The review names concrete risks or confirms the change is safe.; The review output is ordered and actionable for the next agent..
7. [AND] Test stage: Run the relevant automated tests for the changed workflow behavior. Acceptance: Targeted tests pass after the implementation change.; The failure mode is observable if the stage structure regresses..
8. [AND] Ship stage: Make the workflow output usable as a release-grade handoff artifact. Acceptance: The generated workflow includes both stage structure and the legacy `steps` list.; Compose output remains stable across repeated runs with the same inputs..
9. [AND] Reflect stage: Summarize what the evidence says about the current run. Acceptance: Reflection text is grounded in the run's actual feedback or retry state.; Any mode suggestion comes from the current evidence, not a dummy rule..
10. Load the top relevant skills: test_repair_skill.
11. Verification loop: run 1 verification pass before completion.
12. Run the most relevant test or validation command before completion.
