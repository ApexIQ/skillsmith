# Recipe: CI Gate Flow (`ready` + `report --artifact-dir`)

Goal: fail fast on readiness blockers and keep a machine-readable artifact bundle.

Use this as the default CI path for normal repos. Keep advanced/admin commands such as `audit --strict`, `registry-service`, and `trust-service` out of the default gate unless you explicitly need them.

## Commands

```bash
skillsmith ready
skillsmith report --artifact-dir .agent/reports/readiness
```

## Expected Result

- `ready` exits non-zero when blockers remain.
- `report --artifact-dir` writes readiness artifacts into the chosen directory.
- CI can upload that directory as a build artifact.

## Recommended Automated Test Matrix

Keep the gate broad enough to catch regressions, but small enough to stay fast:

- Packaging: `python scripts/check_package_quality.py`
- Docs and contract tests: `python -m unittest -v tests.test_docs_recipes tests.test_stability_contract tests.test_public_api tests.test_cli_version`
- Core workflow and readiness tests: `python -m unittest -v tests.test_quickstart_smoke tests.test_ready_command tests.test_readiness_artifacts tests.test_doctor_behavior`
- Machine output contract tests: `python -m unittest -v tests.test_machine_output_contract`

This keeps the default path centered on `start` + readiness while still validating packaging, docs, public API, quickstart behavior, and deterministic JSON contracts.
