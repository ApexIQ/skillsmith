# Workflow: test-changes

## Summary
- Goal: test and verify changes for library click, pytest, arch-business-logic, arch-ui, arch-unknown
- Project idea: Project using skillsmith
- Skills: javascript_testing_patterns, notebooklm, temporal_python_testing, makepad_skills, loki_mode

## Steps
1. Read .agent/project_profile.yaml and .agent/context/project-context.md.
2. Confirm the requested goal against the current project stage and target tools.
3. [AND] Discover stage: Read .agent/project_profile.yaml and .agent/context/project-context.md before taking action. Acceptance: Project profile and generated context are present or inferred without error.; The ranked skill list is deterministic for the current goal and profile..
4. [OR] Plan stage: Turn the goal into a minimal patch plan with explicit verification checkpoints. Acceptance: The plan names concrete files, commands, or subsystems.; Every planned step has at least one verification check..
5. [OR] Build stage: Implement the smallest coherent change needed for the goal. Acceptance: The patch changes only the files needed for the requested goal.; The requested behavior is present in the generated workflow output..
6. [AND] Review stage: Inspect the changed files for correctness, regressions, and missing coverage. Acceptance: The review names concrete risks or confirms the change is safe.; The review output is ordered and actionable for the next agent..
7. [AND] Test stage: Identify the highest-risk behavior and the smallest reliable test surface. Acceptance: Run the relevant automated tests and record the evidence.; The failure mode is observable if the stage structure regresses..
8. [AND] Ship stage: Make the workflow output usable as a release-grade handoff artifact. Acceptance: The generated workflow includes both stage structure and the legacy `steps` list.; Compose output remains stable across repeated runs with the same inputs..
9. [AND] Reflect stage: Summarize what the evidence says about the current run. Acceptance: Reflection text is grounded in the run's actual feedback or retry state.; Any mode suggestion comes from the current evidence, not a dummy rule..
10. Load the top relevant skills: javascript_testing_patterns, notebooklm, temporal_python_testing, makepad_skills, loki_mode.
11. Verification loop: run 1 verification pass before completion.
12. Run the most relevant test or validation command before completion.
