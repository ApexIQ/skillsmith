# UPCOMING_FEATURES.md

Date: 2026-03-21  
Horizon: Next 30 days  
Decision rule: optimize for one fundable wedge only: `pip install skillsmith` -> `init` -> `compose` -> user ships real change.

## 1) Reality Check (Current Snapshot)

This is the current truth based on repo evidence:

- Product capability is broad and technically strong (large command surface, strong test depth, rich trust/eval/context features).
- PMF signal is weak relative to scope.
- A core release-quality gap still exists:
  - Full test suite currently has 1 failure in README command parity (`roles` command docs drift).
  - Core project setup files are missing in this workspace (`.agent/project_profile.yaml`, `.agent/context/project-context.md`) and flagged by `doctor`/`audit`.

Investor interpretation:

- Strong builder signal.
- Not yet "fund now" signal because core wedge clarity and operational sharpness are diluted by breadth.

## 2) Overengineering Assessment (Keep / Trim / Defer)

### Keep (Core Wedge)

- `init --guided`, `doctor`, `compose`, `report`, `audit`.
- Local-first skill discovery and profile alignment.
- Deterministic machine outputs for core automation paths.

### Trim (Default Surface Reduction)

- Keep advanced commands available, but remove them from the default onboarding story and beginner docs.
- Treat non-core surfaces as "advanced mode", not first-class for new users.

### Defer (Post-PMF)

- Additional enterprise depth beyond current implementation:
  - OIDC expansion and auth-policy complexity
  - trust authority hardening beyond local MVP
  - registry/trust service scale-out concerns
- Any new major command group not directly improving first-time success, activation, or retention.

## 3) 30-Day Plan (Fundability-Oriented)

## Week 1: Baseline Integrity

Goal: eliminate credibility leaks.

Deliverables:

1. Fix README parity failure for `roles` command.
2. Ensure `.agent/project_profile.yaml` and `.agent/context/project-context.md` are consistently generated in local workflows.
3. Re-run full suite and publish clean evidence.

Exit criteria:

- `uv run python -m unittest discover tests -v` passes.
- `skillsmith doctor --json` shows no missing core profile/context artifacts in a fresh initialized repo.

## Week 2: Wedge Compression

Goal: one obvious happy path for new users.

Deliverables:

1. Rewrite docs/navigation so 80% of users only see:
   - install
   - init
   - doctor
   - compose
   - report/audit before merge
2. Move enterprise/advanced material into dedicated advanced sections.
3. Add one activation-focused quickstart smoke path in CI.

Exit criteria:

- New user can copy/paste one path and get successful compose in <10 minutes.
- No required manual file edits in happy path.

## Week 3: Outcome Proof

Goal: show the product helps users ship.

Deliverables:

1. Add outcome-focused examples from real tasks (before/after workflow evidence).
2. Standardize one KPI artifact format for:
   - time to first successful compose
   - compose-to-implemented task completion rate
   - repeat usage in 7 days
3. Ship lightweight instrumentation/reporting for these KPIs (local artifact-first, no mandatory hosted infra).

Exit criteria:

- At least one reproducible benchmark pack demonstrates measurable improvement on core flow.

## Week 4: Investor-Ready Narrative Pack

Goal: convert technical depth into a simple funding story.

Deliverables:

1. One-page "why now / why us / why this wedge" summary grounded in repo evidence.
2. Metrics snapshot for activation, retention, and reliability trends.
3. Explicit roadmap split:
   - next 60 days: PMF acceleration
   - post-PMF: enterprise and platform expansion

Exit criteria:

- Narrative and metrics can answer: "Why this instead of Continue/Aider/Cursor workflows?"

## 4) Hard No List (Next 30 Days)

Do not ship unless it directly improves wedge metrics:

1. New large command families.
2. New remote provider classes beyond current set.
3. New enterprise auth/trust infrastructure depth.
4. UI/dashboard expansion.

## 5) Release Gate (Must Pass)

All must be true by end of this cycle:

- [ ] Full tests green on main.
- [ ] README command parity tests green (including `roles`).
- [ ] Fresh install -> init -> doctor -> compose validated in clean environment.
- [ ] Core docs are wedge-first, advanced features clearly separated.
- [ ] KPI artifact exists and is updated from real runs.

## 6) Funding Readiness Rule

Do not optimize for "more features".  
Optimize for this evidence package:

1. Reliability: green suite, stable core behavior.
2. Clarity: one user story that is easy to explain.
3. Outcomes: measurable user success and repeat usage.
4. Focus: advanced/enterprise depth intentionally staged behind PMF.

If this package is strong, the `$500k` conversation becomes realistic.
