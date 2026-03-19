# Skillsmith: Current vs Expected vs Next Build

Date: 2026-03-20

## Current vs Expected

| Area | Current (today) | Expected (competitive baseline) | Gap |
| --- | --- | --- | --- |
| Onboarding | `init --guided`, profile + context generated | Guided setup + continuous profile refresh + quality gates | Partial |
| Discovery | Local + `skills.sh` + `huggingface` + `github-topics` + `org-registry` discovery, ranking, explainability | Multi-source robust discovery with typed errors and retries | Low |
| Trust/Policy | Policy fields + trust thresholds + pinned refs + remote publisher signature verification policy + revocation + transparency log + centralized authority feeds (signed bundles/revocations/bootstrap roots) | Cryptographic provenance, signatures, pinned refs, attestations | Low |
| Lockfile Integrity | Checksum/provenance fields in `skills.lock.json` | Full tree hashing + signed lockfile + tamper-evident verification | High |
| Auditability | `doctor`, `audit`, `report` with eval policy/context freshness/registry governance and machine outputs | Complete large-scale audit (all installed skills), machine outputs | Low |
| Workflow Surfaces | Workflow bundles + tool-specific render targets | Auto-routing + confidence gating + hook-based execution controls | Medium |
| Context Engine | Project context markdown + profile-driven alignment + `context-index` freshness/compression artifact | Retrieval index, freshness stamps, compressed context artifacts | Medium |
| Runtime Orchestration | Planner/editor + retries + reflection + rolling eval-feedback tuning + SLO-budget-governed adaptive clamps | Planner/editor split, retries, reflection loop, parallel lanes | Low |
| Evaluation | Built-in eval artifacts + trend + CI regression gates + policy-resolved SLO budgets in artifacts | Built-in benchmark harness (quality/cost/latency/intervention) | Low |
| Ecosystem Distribution | Skill install + registry governance + multi-tenant service APIs + RBAC + sync clients | Team/private/public registries, governance, sharing, lifecycle states | Medium |

## What Competitors Are Doing Better

1. Productized runtime workflows (hooks, memories, worktrees, workflow automation) are first-class in IDE-native agents.
2. Reliability loops are explicit (plan mode, constrained action flows, retry/repair behavior).
3. Evaluation is becoming a moat (SWE-bench style reporting, leaderboard-style measurement, measurable resolved-rate progress).
4. Enterprise trust expectations are moving beyond metadata trust scores toward stronger provenance controls.

## Proven Workflow Patterns (Papers + HF Guidance)

1. ReAct loop: explicit Thought -> Action -> Observation for robust tool-use execution.
2. Toolformer: improve tool-selection behavior with structured tool-usage patterns.
3. Reflexion/Self-refine style retries: post-run critique and second-pass repair improves success rates.
4. SWE-agent/ACI: constrained agent-computer interfaces improve coding-agent reliability.
5. Hugging Face agent guidance: keep loops explicit, use modular tools, and preserve observation traces for debugging/evals.

## Prioritized Build Next (Execution Backlog)

### P0 (Build now: 1-2 weeks)

1. Lockfile hardening v2 (`Done`)
   - Add schema version + atomic writes.
   - Replace `SKILL.md`-only checksum with full skill directory manifest hash.
   - Done when tampering in any installed skill file is detected by `doctor --strict`.
2. Discovery reliability pass (`Done`)
   - Replace broad `except Exception` paths with typed provider errors.
   - Add user-visible diagnostics for provider failures.
   - Add bounded retry/backoff and provider telemetry.
3. Audit completeness fix (`Done`)
   - Remove `skills[:10]` truncation in `doctor`, `audit`, `report`.
   - Done when large lockfiles are fully inspected and covered by tests.

### P1 (Build next: 2-4 weeks)

1. `skillsmith eval` command (MVP) (`Done`)
   - Define task set + metrics: pass rate, policy pass, cost, latency, interventions.
   - Store run artifacts for regression comparisons and trend deltas.
2. Planner/editor split mode (`Done`)
   - Planning stage proposes patch plan; editor stage applies deterministic edits.
   - Add fallback/retry policy scaffolding.
3. Reflection loop (`Done`)
   - On failure, capture structured failure memory and run one bounded retry.

### P2 (Build after: 1-2 months)

1. Signature and provenance model (`Done`)
   - Optional signature bundle verification for remote skills.
   - Commit SHA pinning for GitHub installs.
2. Context artifact v2 (`MVP Done`)
   - Retrieval-friendly context index + freshness stamps.
3. Team registry and governance (`MVP Done`)
   - Support private/org skill catalogs, allow/block policies, and approval workflow.

## Task Board: Current vs Expected

| Task | Current Status | Expected Status | Next Action |
| --- | --- | --- | --- |
| Full skill integrity verification | Done (+ remote publisher signature checks, HMAC+RSA, revocation+transparency log, centralized signed authority feeds) | Complete | Add external trust anchor management (KMS/HSM-backed roots) |
| Deterministic remote installs | Done | Complete | Add third-party/verifiable attestation sources |
| Provider failure diagnostics | Done | Strong | Add provider SLO alerts and trend regression checks |
| Large-install audit coverage | Done | Strong | Keep scale tests in CI |
| Agent reliability loop | Runtime Feedback + policy-bounded adaptive tuning Done | Present | Add per-team override policy with audit approvals |
| Product quality metrics | MVP+Trend+CI Gates+Dashboard+SLO Budgets Done | Present | Add benchmark suites and release-stage quality scorecards |
| Retrieval-grade context layer | MVP Done (`context-index`) | Strong | Add richer retrieval scoring + embeddings |
| Registry/governance moat | Multi-tenant + RBAC service baseline Done | Strong | Add durable external datastore + OIDC/SSO authN |

## Suggested North-Star Metric

Trusted Autonomous Completion Rate (TACR):

`% of tasks completed end-to-end where tests pass + policy checks pass + no rollback required`
