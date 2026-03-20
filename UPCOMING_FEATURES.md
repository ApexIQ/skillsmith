# UPCOMING_FEATURES.md

Date: 2026-03-21  
Horizon: Next 30 days  
Decision rule: optimize for one promise only: `pip install skillsmith` -> project is agent-ready without extra infrastructure.

## 1) Current Baseline (As of 2026-03-21)

Already shipped and verified:

- Core CLI/library flow exists: `init`, `align`, `doctor`, `discover`, `add`, `compose`, `eval`, `report`, `audit`.
- Runtime packaging is reduced and asset bootstrap exists.
- Core governance/trust/context features exist (including optional registry/trust service surfaces).
- Durable local service persistence and optional OIDC/signer paths now exist.
- Full suite is green.

What is true right now:

- The product has many capabilities, but the default “library-first golden path” is not yet simplified enough for fast new-user success.
- Core UX, docs, and stability guarantees are still less clear than they need to be for broad Python-library adoption.

## 2) Top 5 Upcoming Features (Next 30 Days, Library-First)

Each feature is scoped to 2-4 days of focused work.

### Feature 1: Golden Path Installer Experience

- Problem statement:
  - New users can install, but first successful run is still too fragmented.
- Why now:
  - Adoption depends on time-to-first-success, not feature depth.
- Smallest shippable slice:
  - One canonical flow: `pip install skillsmith` -> `skillsmith init --guided` -> `skillsmith doctor` -> `skillsmith compose`.
  - Add one copy-paste quickstart block in README that is tested in CI.
- Success metrics:
  - Fresh machine setup to first successful compose in <10 minutes.
  - Zero manual file edits required for the happy path.
- Acceptance checks (binary):
  - [x] Quickstart commands run successfully in a clean temp project.
  - [x] README quickstart matches real command behavior exactly.
  - [x] CI includes one smoke test executing the same sequence.
- Dependencies and risks:
  - Dependency: stable command defaults.
  - Risk: drift between docs and behavior.

### Feature 2: Public API/CLI Stability Contract (v0.x hardening)

- Problem statement:
  - Users cannot rely on a clear stability policy for library and CLI surfaces.
- Why now:
  - Trust in a Python library comes from predictable upgrades.
- Smallest shippable slice:
  - Define and publish “stable vs experimental” surfaces for CLI and Python imports.
  - Add deprecation warning behavior and migration notes template.
- Success metrics:
  - Every user-facing command/import mapped to stability tier.
  - Breaking changes fail contract checks in CI.
- Acceptance checks (binary):
  - [x] `README` + `STATE` document the stability contract.
  - [x] At least one automated check fails when command surface drifts without docs update.
  - [x] Deprecation path is tested for one representative command option.
- Dependencies and risks:
  - Dependency: command surface inventory.
  - Risk: hidden surface area in tests/docs mismatch.

### Feature 3: Core Reliability Pack (Deterministic Defaults)

- Problem statement:
  - Advanced behavior exists, but core outputs are not yet deterministic enough for teams and CI.
- Why now:
  - Reliability beats breadth for a core library.
- Smallest shippable slice:
  - Tighten deterministic output paths for `compose`, `recommend`, `doctor` machine outputs.
  - Enforce strict JSON schemas for machine-consumed commands.
- Success metrics:
  - Repeat runs with same inputs produce stable machine outputs.
  - Core command regressions detected before merge.
- Acceptance checks (binary):
  - [x] JSON schema checks added for core machine outputs.
  - [x] Snapshot-style regression tests pass for deterministic paths.
  - [x] No flaky tests in core command suite across 3 repeated runs.
- Dependencies and risks:
  - Dependency: explicit schema definitions.
  - Risk: over-constraining output evolution.

### Feature 4: Docs-as-Product for Python Users

- Problem statement:
  - Current docs are broad, but not focused enough on library adoption tasks.
- Why now:
  - For Python libraries, docs quality is product quality.
- Smallest shippable slice:
  - Publish 3 production-oriented recipes:
    - local project bootstrap
    - CI gate flow (`doctor` + `eval`)
    - team onboarding flow with minimal config
  - Add “failure recovery” section with exact commands.
- Success metrics:
  - New user can complete any recipe without source-code reading.
  - Support questions about basic setup reduced.
- Acceptance checks (binary):
  - [x] Three recipe docs added and command-verified.
  - [x] Failure recovery section includes at least 5 concrete failure modes + fixes.
  - [x] Links and command snippets validated in CI.
- Dependencies and risks:
  - Dependency: stable quickstart behavior.
  - Risk: docs drift if command output changes.

### Feature 5: Minimal Python SDK Entry Points

- Status: partially complete; minimal import-first SDK entry points are implemented and documented, with remaining contract/test hardening pending.

- Problem statement:
  - CLI is strong, but Python-native embedding path is still unclear for users integrating into their own tools.
- Why now:
  - “Best Python library” requires a clean import-first API.
- Smallest shippable slice:
  - Add documented Python API entry points for 3 core operations:
    - bootstrap/init flow
    - compose workflow generation
    - health checks/doctor summary
  - Keep thin wrappers over existing command internals.
- Success metrics:
  - Python users can perform core flow without shelling out.
  - SDK examples run in CI.
- Acceptance checks (binary):
  - [x] `from skillsmith import ...` examples exist and pass tests.
  - [x] API signatures documented and type-annotated.
  - [x] Semver notes include SDK surface commitments.
- Dependencies and risks:
  - Dependency: decide official public module paths.
  - Risk: exposing unstable internals too early.

## 3) Execution Sequence (Week 1-4)

### Week 1

- Priority items:
  - Feature 1 (Golden path)
  - Feature 4 (Docs quickstart + recovery)
- Owner roles:
  - Orchestrator: lock exact first-run flow and success criteria.
  - Researcher: identify current friction points from baseline commands/docs.
  - Implementer: command default tuning + docs updates.
  - Reviewer: clean-environment replay and doc-command parity check.
- Verification evidence:
  - Clean env run log for quickstart sequence.
  - `uv run python -m unittest tests.test_commands -v` (targeted core checks).

### Week 2

- Priority items:
  - Feature 2 (stability contract)
  - Feature 3 (deterministic JSON/schema checks)
- Owner roles:
  - Orchestrator: define stable vs experimental list.
  - Researcher: enumerate surface area and drift risk.
  - Implementer: contract docs + CI checks + schema assertions.
  - Reviewer: regression pass on repeated runs.
- Verification evidence:
  - Contract check output in CI.
  - Repeated-run determinism proof (3-run consistency report).

### Week 3

- Priority items:
  - Feature 5 (minimal SDK entry points)
  - Finish remaining determinism/test debt from Week 2
- Owner roles:
  - Orchestrator: bound SDK scope to 3 APIs only.
  - Researcher: identify safe public import boundaries.
  - Implementer: API wrappers + typed docs + examples.
  - Reviewer: API backward-compat and test quality check.
- Verification evidence:
  - SDK example tests passing.
  - Core suite still green.

### Week 4

- Priority items:
  - Integration hardening and release prep.
- Owner roles:
  - Orchestrator: release gate decision.
  - Researcher: release-risk checklist.
  - Implementer: fix release blockers only.
  - Reviewer: full regression + docs parity final pass.
- Verification evidence:
  - `uv run python -m unittest discover tests -v` green.
  - quickstart replay from scratch still green.

## 4) Do Not Build Now

Explicitly deprioritized this cycle:

1. Additional enterprise infrastructure depth (full KMS/HSM integrations, distributed service clustering)
- Reason:
  - Valuable, but not needed for the default Python-library promise.
- Re-entry trigger:
  - After library-first release gate is fully green and core adoption metrics are positive.

2. Large new command-surface expansion
- Reason:
  - More commands increase cognitive load and docs drift risk.
- Re-entry trigger:
  - Only after current core commands show stable usage and low support friction.

3. Broad provider/catalog expansion
- Reason:
  - Current blocker is reliability/UX, not provider count.
- Re-entry trigger:
  - After deterministic output + docs parity + SDK baseline are complete.

4. Major UI/dashboard buildout
- Reason:
  - The product promise here is Python library + CLI first.
- Re-entry trigger:
  - When CLI-first users explicitly demand UI for daily workflows.

## 5) Release Gate (End of 30 Days)

Month is successful only if all are true:

- [x] Fresh install quickstart works exactly as documented.
- [x] Core contract (stable vs experimental surfaces) is published and enforced.
- [x] Deterministic machine outputs for core commands are schema-checked and regression-tested.
- [x] Minimal Python SDK entry points are documented, tested, and usable.
- [x] `uv run python -m unittest discover tests -v` passes on main.
- [x] `.agent/STATE.md` updated with objective evidence.

Mandatory evidence bundle:

- Clean-environment quickstart transcript.
- Contract/surface check output.
- Determinism and schema test results.
- SDK usage examples and passing tests.
- Full regression test output.
