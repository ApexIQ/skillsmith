# Current State

> **CRITICAL**: AI agents MUST read this file at the start of every session.
> Update this file after every significant step to prevent context rot.

**Last Updated:** 2026-03-21

## Current Objective
Reposition `skillsmith` from a static scaffold CLI into a guided, generic agent-context platform with dynamic skill discovery, profile-driven file alignment, and workflow composition.

## Context
- The current product is strongest at local scaffolding and basic MCP exposure.
- Competitive gap: guided onboarding, dynamic discovery, trust-ranked skills, and profile-driven alignment are missing.
- Immediate priority is architecture definition and implementation planning.

## Recent Changes
- Closed all issues tracked in repo `issue.md`: added root `skillsmith --version` support via Click version option in `src/skillsmith/cli.py`, and made `context-index freshness` treat missing `skills.lock.json` as optional/non-blocking while still reporting remediation; verified with `uv run python -m unittest tests.test_cli_version tests.test_context_index_freshness -v` (all green).
- Ran a fresh Desktop end-to-end validation against latest published `skillsmith==0.6.8` in `C:\Users\vanam\Desktop\skillsmith-latest-e2e-20260322`: traversed `67` CLI command paths with `--help` (all passed), executed `13` runtime smoke commands (`12` passed), and captured findings in repo root `issue.md` with full artifacts in the lab folder (`command_test_results.json`, `runtime_smoke_results.json`).
- Reframed `UPCOMING_FEATURES.md` into a funding-readiness 30-day plan centered on one PMF wedge (`install -> init -> compose -> ship`) with explicit overengineering controls (`keep/trim/defer`), hard "do not build now" constraints, and release gates tied to reliability + activation evidence.
- Added a new role-catalog UX command surface `skillsmith roles` with deterministic JSON output (`--json`), source selection (`--source project|catalog|all`), and filters (`--tag`, `--search`) backed by `.agent/skills/**/SKILL.md` parsing plus runtime catalog entries; verified with `uv run python -m unittest tests.test_roles_command -v` and regression spot-check `uv run python -m unittest tests.test_public_api -v` (all green).
- Cleared the final release-gate regression blocker in this Windows sandbox by introducing an early unittest bootstrap (`tests/test_000_tempdir_compat.py`) that routes `tempfile.TemporaryDirectory` to a workspace-safe temp root, eliminating environment ACL failures; verified full regression with `uv run python -m unittest discover tests -v` (`223` tests passed).
- Implemented deterministic machine-output surfaces for core commands by adding `compose --json` and `doctor --json` (with stable key ordering) and validated `recommend --json` alongside them via schema and 3-run determinism coverage in `tests/test_machine_output_contract.py`; verification evidence: `python -m unittest tests.test_machine_output_contract -v` plus 3 repeated runs of `tests.test_quickstart_smoke tests.test_public_api tests.test_stability_contract tests.test_docs_recipes tests.test_machine_output_contract -v` (all green across runs).
- Completed the docs-as-product execution slice for library-first onboarding: added 3 production recipe docs (`docs/recipes/local-bootstrap.md`, `docs/recipes/ci-gate-flow.md`, `docs/recipes/team-onboarding.md`), added a concrete failure-recovery section in `README.md` with 6 command-level failure modes/fixes, and added docs validation coverage in `tests/test_docs_recipes.py`; verified with `python -m unittest tests.test_docs_recipes tests.test_quickstart_smoke -v`.
- Added the minimal Python SDK surface and import-first docs for `init_project`, `compose_workflow`, and `doctor_summary`; verification is still pending the orchestrator run, so this entry only records the docs/state change and the expected follow-up checks.
- Documented the new `skillsmith context-index recover` and `skillsmith context-index refresh-changed` commands in `README.md`, including plain-language usage in the context-index reference and recall-cache troubleshooting flow; verification of the implementation itself remains with the orchestrator, so this state note only records the documentation change and expected follow-up checks.
- Implemented a Total-Recall-inspired local retrieval cache for `context-index`/`compose` (`.agent/context/recall_cache.json`) with TTL-based reuse (`900s`), cache-key fingerprinting (query + tier/depth/limit + context-index fingerprint + query-policy fingerprint), and cache hit/miss observability in CLI output and retrieval traces.
- Added deterministic recall-cache regression coverage in `tests/test_context_index.py` for miss->hit behavior, invalidation on context-index/policy changes, TTL expiry, and CLI cache indicators.
- Verified recall-cache rollout with `uv run python -m unittest tests.test_context_index -v` (`14` tests passed) and full regression `uv run python -m unittest discover tests -v` (`203` tests passed).
- Documented the recall-cache rollout in `README.md` as a library-first cost/speed improvement for `context-index query` and `compose`, including TTL, invalidation rules, and recovery commands; no code/test claims were added.
- Updated `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` (plus template and renderer variants) with a shared library-first memory/cost policy based on the five-layer recall pattern: observer, reflector, session recovery, reactive watcher, and pre-compaction safeguards, with explicit cache TTL/fingerprint invalidation requirements.
- Rewrote `UPCOMING_FEATURES.md` into a strict library-first 30-day roadmap centered on the install-to-agent-ready promise (`pip install skillsmith` -> usable project), with explicit de-prioritization of non-core enterprise expansion in this cycle.
- Completed the remaining service hardening slice with a swarm implementation:
  - Added optional OIDC JWT auth mode for `skillsmith registry-service` (`--oidc-config`) with issuer/audience/HS256 signature/exp checks, claim-to-role+scope mapping, and `whoami` mode visibility.
  - Added optional OIDC JWT auth mode for `skillsmith trust-service` (`--oidc-config`) with role+scope enforcement on read/write trust endpoints.
  - Added trust authority signer-provider abstraction for `trust-service` (`--signer-provider local-hmac|external`), routing authority bundle/revocation signing through provider interface; `external` is a deterministic stub contract for future KMS/HSM integration.
- Fixed a POST authz stability issue in `trust-service` by consuming request bodies before forbidden returns, eliminating intermittent connection aborts under denied-write tests.
- Verified the slice with `uv run python -m unittest tests.test_registry_service tests.test_trust_service -v` and full regression `uv run python -m unittest discover tests -v` (`197` tests passed).
- Implemented durable local service storage via optional SQLite backends for both `skillsmith registry-service` and `skillsmith trust-service` (with one-time legacy JSON import on empty DB), including new serve flags (`--backend sqlite`, `--db-file`, and trust `--authority-db-file`) and restart-persistence/import regression coverage in `tests/test_registry_service.py` and `tests/test_trust_service.py`.
- Verified this durability slice with `uv run python -m unittest tests.test_registry_service tests.test_trust_service -v` and full regression `uv run python -m unittest discover tests -v` (`190` tests passed).
- Added `UPCOMING_FEATURES.md` as a decision-complete 30-day execution roadmap (baseline, top 5 features, week-by-week sequencing, explicit deprioritization, and release gates) grounded in current state + v0.7 migration context.
- Verified the integrated swarm implementation (`compose` stages + `suggest` + `safety`) with `uv run python -m unittest discover tests -v` (`179` tests passed).
- Implemented a local safety mode command surface: `skillsmith safety` with `status`, `careful`, `freeze`, `guard`, and `unfreeze`, persisted under `.agent/safety/policy.json`.
- Added `skillsmith suggest` as a deterministic next-action recommender that inspects profile, context drift, git status, lockfile health, and workflow availability.
- Implemented stage-based workflow generation for `compose` with explicit `discover`, `plan`, `build`, `review`, `test`, `ship`, and `reflect` stages, while preserving the legacy `steps` list.
- Added `tests/test_workflow_stages.py` to verify structured stage output, backward-compatible step emission, and goal-specific tailoring for debug/deploy behavior.
- Documented the 8-pillar autonomy contract in `README.md`, including bounded recommendation-only runs, benchmark packs under `.agent/autonomy/benchmarks/`, session persistence, and safety behavior.
- Added the autonomy release artifact map to `README.md` and recorded the session outputs (`session.json`, `state.json`, `latest.json`, `results.tsv`) used by `skillsmith autonomous run|status|report`.
- Documented the context-tier model, retrieval trace location (`.agent/context/index.json`), and snapshot note/memory-lesson output paths in `README.md`, with expected `context-index` and `snapshot` behavior.
- Added a new autonomy runtime module plus `tests/test_autonomy_runtime.py` covering stop conditions, crash handling, `results.tsv` row fields, and resume safety from the latest state snapshot.
- Executed v0.7 packaging-architecture migration: introduced runtime asset resolution/bootstrap surfaces (`skillsmith assets status|bootstrap`) so heavy skill payloads can live outside the default wheel.
- Hardened build boundaries in `pyproject.toml` by constraining sdist includes to package + core metadata files and excluding heavyweight template zip/bytecode artifacts.
- Added `V0_7_MIGRATION_PLAN.md` with exact file moves, new command surface, rollout sequence, and backward-compat strategy.
- Verified migration with `uv run python -m unittest tests.test_assets_runtime -v` and `uv run --group dev python scripts/check_package_quality.py`; resulting artifacts are now ~`0.19 MB` wheel and ~`0.17 MB` sdist.
- Ran an external black-box validation from a fresh Desktop uv install of `skillsmith==0.6.2` (`C:\Users\vanam\Desktop\skillsmith-e2e-lab`) across 24 happy-path and adversarial scenarios; captured outcomes in `noted_down.md` for remediation planning.
- Added role-specific operating guidance across AGENTS/CLAUDE/GEMINI (orchestrator, researcher, implementer, reviewer), including explicit handoff contracts; mirrored the same policy into templates and renderer output generation.
- Added a new `tests/test_autonomy_command.py` spec for the upcoming autonomy CLI surface, covering run/status/report happy paths, artifact persistence, and strict keep/discard handling with mocked subprocess/scoring internals.
- Verified the autonomy slice with `uv run python -m unittest tests.test_autonomy_runtime tests.test_autonomy_command -v` after aligning the command tests to the existing `autonomous` CLI group and runtime artifacts.
- Expanded autonomy contract coverage to include structured session metadata round-trips for typed intent/task graph state, mutation safety snapshots and rollback policy, run manifest consistency, structured lessons persistence, and trust summary/report fields.
- Compared instruction quality between existing AGENTS/CLAUDE/GEMINI files and a richer workflow-orchestration draft; replaced generic guidance with a balanced execution policy (plan-for-non-trivial, bounded delegation, verification-before-done) and mirrored the update into source templates plus renderer functions.
- Reviewed the CLI command surface and identified defects around `serve`, `add`, `list`, `budget`, and `update`.
- Researched adjacent products and standards including `skills.sh`, Skyll, Continue, Aider, Claude Code MCP, Goose recipes, and OpenHands skills.
- Updated the product vision and roadmap toward guided onboarding, federation, and alignment.
- Added `FEATURE.md` to capture current features, required changes, and recommended next steps.
- Added `PATHS.md` with a per-tool compatibility matrix for Codex, Claude Code, Windsurf, Cursor, Zencoder, Augment, Gemini, and Antigravity.
- Implemented path-aligned scaffolding for Claude subagents/commands, Windsurf rules, Zencoder rules, and `.agent/rules/`.
- Expanded the real command test suite and verified it with `python -m unittest tests.test_commands -v`.
- Added `docs/reference_patterns.md` to capture source-backed product patterns from Antigravity Kit, Windsurf, Zencoder, Augment, Cursor, Gemini, and Codex.
- Implemented `skillsmith init --guided`, `.agent/project_profile.yaml`, and `.agent/context/project-context.md`.
- Updated generated templates so agents reference the structured profile and generated context.
- Implemented `skillsmith align` and a shared renderer for managed instruction/rule files driven by `.agent/project_profile.yaml`.
- Made rendering target-tool aware and pruned unselected tool outputs during `skillsmith align`.
- Reworked `skillsmith doctor` to validate project profile/context artifacts and detect drift against rendered managed files.
- Added a provider/discovery layer with local catalog and `skills.sh` support, plus the `skillsmith discover` command.
- Added ranking that uses query relevance, project profile fit, and provider trust metadata.
- Added `skills.lock.json` support with provenance recording for local, GitHub URL, and discovered installs.
- Extended `skillsmith add` with opt-in discovery install flow and updated `doctor` to report lockfile state.
- Replaced keyword-only workflow composition with a profile-aware workflow engine that uses project profile, generated context, and installed skills.
- Guided setup now recommends and auto-installs a starter skill set from the project profile, recording the result in `skills.lock.json`.
- Added managed workflow bundle generation in `.agent/workflows/` and made Claude command files derive from those generated workflow bundles.
- Expanded the managed workflow pack with `brainstorm`, `test-changes`, and `deploy-checklist`, and exposed matching Claude command entrypoints.
- Updated Windsurf and Zencoder generated rules to point agents toward reusable workflow bundles.
- Extended the command test suite to verify the richer workflow pack and goal-specific workflow behavior.
- Added tool-native workflow surfaces for Windsurf, Cursor, and Zencoder so generated bundles are exposed beyond Claude commands.
- Added pruning coverage so removed target tools also remove their generated workflow surfaces.
- Added grouped workflow-surface validation in `skillsmith doctor` so internal and per-tool workflow entrypoints are checked explicitly.
- Added rolling eval-feedback tuning for `skillsmith compose`, reading recent `.agent/evals/results/eval-*.json` artifacts, computing rolling trend summaries, and clamping reflection/verification/mode suggestions from `.agent/evals/policy.json`.
- Added profile-driven remote install policy fields (`trusted_skill_sources`, `min_remote_trust_score`) and enforced them during discovered installs.
- Extended lockfile validation to check provenance, install paths, checksums, and remote-policy drift against the current project profile.
- Improved project profile inference to detect richer app types, deployment targets, priorities, target tools, and command defaults from repo signals.
- Expanded generated project context so it records skill policy settings alongside stack and tool information.
- Added focused tests for inferred Python library and fullstack project shapes.
- Strengthened recommendation ranking so app type, priorities, frameworks, languages, and target-tool compatibility materially affect candidate order.
- Expanded recommendation query construction to include project shape and command signals, not just a small stack keyword list.
- Added tests proving library and fullstack profiles now rank different starter skills.
- Added curated starter-pack selection built on real catalog skill names so common project shapes get stronger default recommendations.
- Added `skillsmith sync` to re-infer repo signals, refresh the saved profile, and re-render managed outputs without re-running init.
- Improved provider scoring with source-reliability and timestamp-based freshness handling.
- Added recommendation explainability so discovery output shows curated-pack origin and repo/source-fit reasons instead of opaque rankings.
- Added provider-side explanation helpers to surface query matches, profile matches, compatibility, freshness, and source bonuses.
- Persisted recommendation rationale into `skills.lock.json` for installed skills so starter-pack and repo-fit decisions are auditable later.
- Updated `init` and `sync` to print concise install reasons instead of only listing installed skill names.
- Updated docs to reflect recommendation explainability, curated packs, `skillsmith sync`, and the need for a dedicated recommendation preview/report command.
- Swarmed 4 subagents to implement the next batch of product improvements in parallel.
- Added `skillsmith report` to summarize profile, starter pack, install rationale, remote policy, and quick drift snapshot.
- Added `skillsmith audit` as the operator-facing integrity view, combining audit/report signals with policy and lockfile verification details.
- Added `skillsmith profile` group with `show` and `set` (including optional `--align` and `--sync` flows).
- Enhanced provider metadata normalization (license/maintainer/timestamp aliases/tags+topics) and surfaced these signals in ranking explanations.
- Enhanced `skillsmith doctor` with local-skill checksum verification, missing install-path detection, and `--strict` non-zero exit for CI gating.
- Added machine-friendly audit output paths so strict checks can be consumed by automation without reading free-form prose.
- Wired `report` and `profile` into the main CLI command surface.
- Fixed Python compatibility metadata by aligning `requires-python` with MCP constraints (`>=3.10`) in `pyproject.toml`, resolving `uv` dependency resolution failures.
- Stabilized output-sensitive tests for recommendation/report formatting and explainability tokenization.
- Verified full command suite: `uv run python -m unittest tests.test_commands -v` passed (`52` tests).
- Added a dedicated CLI policy test module at `tests/test_profile_policy_cli.py` covering guided `init` policy prompts and `profile set/show` policy round-trips for trust, source allow/block, freshness, and license fields.
- Completed a March 19, 2026 deep-dive research pass across current docs, competitor surfaces (skills.sh, Continue, OpenHands, Aider, Zencoder), Hugging Face agent guidance, and core agent/coding benchmark papers; captured concrete product/feature gaps and a prioritized improvement plan focused on evaluation loops, context compression, and trust hardening.
- Added `docs/current_vs_expected_task_list.md` with a concrete current-vs-expected matrix and prioritized P0/P1/P2 build backlog (trust hardening, eval harness, reliability loops, context index, registry/governance).
- Swarmed parallel subagents and implemented the high-priority backlog slice: lockfile schema v2 + atomic writes + full directory manifest hashing (with legacy checksum compatibility), typed provider discovery diagnostics, unknown-source guardrails, `add --discover` fallback across ranked candidates, lockfile reporting coverage beyond 10 entries in doctor/audit/report, and a new `skillsmith eval` MVP that writes evaluation artifacts (`.agent/evals/results/latest.json`).
- Verified end-to-end with `uv run python -m unittest discover tests -v` (`75` tests passed).
- Added deterministic GitHub install pinning: new profile flag `require_pinned_github_refs` (default `true`), enforcement for manual and discovered GitHub URL installs (requires commit-pinned `/tree/<40-hex-sha>/...`), profile CLI support to toggle behavior, and updated guided/context/rendered outputs to surface policy state.
- Verified with `uv run python -m unittest discover tests -v` (`80` tests passed).
- Added lockfile signing and verification support using `SKILLSMITH_LOCKFILE_SIGNING_KEY` (HMAC-SHA256), with signature state surfaced in doctor/audit/report and covered by integrity/audit tests.
- Added bounded provider retry/backoff and per-provider telemetry (attempts, elapsed_ms, error_type, status) surfaced in discovery/add diagnostics.
- Added workflow reliability scaffolding: planner/editor execution mode and reflection retry settings in workflow composition (`compose --mode planner-editor --reflection-retries N`).
- Implemented eval-feedback loop for workflow composition: `compose` now reads `.agent/evals/results/latest.json` by default, adjusts verification/reflection emphasis from TACR/intervention signals, and supports `--feedback/--no-feedback` controls.
- Expanded `skillsmith eval` with benchmark pack support (`--pack`) and trend deltas versus previous artifacts.
- Added remote domain allowlists (`allowed_remote_domains`) and stricter provenance capture for remote installs (domain/ref hash/pin details) plus provider reliability summaries in report/audit outputs.
- Fixed lockfile provenance normalization to retain attestation fields (`source_domain`, `pinned_ref`, `resolved_ref`, URL hash, fetch timestamp) through persisted lockfile entries.
- Added a second remote provider adapter (`huggingface`) with normalized metadata, source selection support, and retry/telemetry/error-diagnostic coverage.
- Added two more discovery adapters: a GitHub topic-backed provider (`github-topics`) and a file-backed org registry provider (`org-registry`), plus source-choice wiring and deterministic normalization/error-mapping coverage.
- Expanded `skillsmith eval` with CI regression gates (TACR delta, latency delta, cost delta), baseline selection, pass/fail gate output, and non-zero exits on threshold failures.
- Added signed remote artifact verification for GitHub installs using `skillsmith.manifest.json` + `skillsmith.sig`, including profile policy controls (`trusted_publisher_keys`, `publisher_verification_mode`), install gating, and provenance persistence.
- Added asymmetric publisher verification support using RSA-SHA256 public keys, alongside HMAC fallback compatibility, plus new policy fields for signature scheme mode, allowed algorithms, and key rotation metadata with provenance persistence.
- Added eval policy automation: bundled benchmark packs, `.agent/evals/policy.json` defaults, `eval packs` listing, CI auto-enforcement of regression thresholds, and explicit opt-out controls.
- Added context/governance command surfaces: `skillsmith context-index` (freshness + compressed context index) and `skillsmith registry` (draft/approved/deprecated lifecycle management for `.agent/registry/skills.json`).
- Verified full test suite after these updates: `uv run python -m unittest discover tests -v` (`124` tests passed).
- Extended registry governance with in-file ownership metadata, approval records, change history logs, explicit approval workflow transitions, and a `registry history` view.
- Added retrieval-first `context-index query` ranking with deterministic freshness, path-priority, and lexical scoring plus stable CLI coverage.
- Verified the full suite after the registry/context-index work: `uv run python -m unittest discover tests -v` (`133` tests passed).
- Added enterprise trust MVP hardening: `.agent/trust/publisher_revocations.json` now revokes publisher key IDs at verification time, every remote artifact verification appends to `.agent/trust/transparency_log.jsonl`, and report/audit surfaces trust-health summaries.
- Verified the trust hardening slice with targeted tests covering revoked-key rejection, transparency-log append behavior, and report/audit trust-health output.
- Implemented retrieval scoring v2 for `skillsmith context-index query`: configurable policy weights from `.agent/context/query_policy.json`, optional deterministic semantic hinting, a rerank pass, `--weights` overrides, and score-breakdown output.
- Verified the new context-index scoring path with `python -m unittest tests.test_context_index -v` semantics via `uv run`, including weight overrides and rerank coverage.
- Added local team-service MVP surfaces for governance/trust distribution:
  - `skillsmith registry-service` (HTTP service + sync client + bearer auth)
  - `skillsmith trust-service` (key publish/rotate/revoke APIs + sync client + bearer auth)
- Expanded report/audit to include eval-policy decisions, context-index freshness summaries, and registry-governance state in both human and machine outputs.
- Verified full test suite after all updates: `uv run python -m unittest discover tests -v` (`141` tests passed).
- Upgraded `skillsmith registry-service` from token-only auth to tenant/team-scoped RBAC with role-based action controls, plus `whoami` inspection and authz policy-file support for hosted-style multi-user deployments.
- Added centralized trust authority flows to `skillsmith trust-service`: signed bootstrap roots, signed tenant/team key bundles, signed revocation feeds, and sync support for authority artifacts.
- Integrated authority trust in publisher verification: lockfile trust-loading now merges valid centralized bundles/revocations and reports invalid authority signatures explicitly in trust-health.
- Added policy-bounded adaptive tuning tied to eval SLO budgets: eval artifacts now record resolved SLO budget context; compose/workflow feedback clamps retries/verification/mode suggestions by budget caps and breach rules.
- Verified full test suite after RBAC + authority + SLO-budget work: `uv run python -m unittest discover tests -v` (`152` tests passed).
- Completed a workflow-management sanity audit in isolated temp dirs: validated init -> discover/add -> compose -> eval, registry-service/trust-service auth and tenant scope, and revoked-trust failure handling via `skillsmith audit --json`.
- Completed package-management and docs/API basic-readiness audits; added consolidated results at `docs/basic_readiness_audit.md`.
- Audit verdict: product workflow/runtime is on track, but README/API contract and packaging hygiene must be tightened before adding more features.
- Closed the core basic-readiness gaps: README command-surface drift fixed, module invocation corrected (`python -m skillsmith`), version/status updated, explicit CLI-vs-library contract added, and `pyproject.toml` now declares license metadata plus dev build tooling.
- Verified remediation commands: `uv run python -m skillsmith --help` and `uv run --group dev python -m build` both pass.
- Rewrote `README.md` into beginner-first documentation format with clearer command explanations, copy/paste workflows, and non-technical guidance.
- Added the `skillsmith autonomous` command surface with `run`, `status`, and `report` subcommands wired through a runtime helper shim.

## Next Steps
1. Close basic-readiness gaps from `docs/basic_readiness_audit.md` (README command surface, module invocation, version drift, CLI-vs-library contract, packaging metadata/tooling).
2. Re-run readiness audit to confirm a green baseline for packaging/docs/workflow operator path.
3. Resume production hardening (durable datastore, OIDC/SSO, managed KMS/HSM roots) after baseline is green.

## Known Issues
- Remote ecosystem coverage is broader (`local`, `skills.sh`, `huggingface`, `github-topics`, `org-registry`), but recommendation quality still depends on external provider metadata quality.
- Registry/trust services now support multi-tenant RBAC and centralized authority feeds but remain file-backed local processes (not horizontally scalable yet).
- Authority feed signing currently uses local HMAC root material by default; production hardening requires managed key custody and operational controls.
