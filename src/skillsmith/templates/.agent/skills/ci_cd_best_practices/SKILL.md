---
version: 0.1.0
name: ci-cd-best-practices
description: Use this skill when setting up or improving CI/CD pipelines. Covers automation, testing, and deployment best practices.
tags: [devops, ci, cd, pipeline, deployment, automation]
---

# 🚀 CI/CD Best Practices

> **Goal:** Ship fast, ship safe, ship often.

## 1. Pipeline Strategy

### For Monorepos
*   **Change Detection:** Only run jobs for changed packages.
*   Tools: Nx, Turborepo, or path filters in GitHub Actions/GitLab CI.

### For Standard Repos
*   Run full pipeline on every push to feature branches.
*   Optimize with caching and parallelization.

## 2. CI: The Feedback Loop
*   **Speed Target:** Pipeline should finish in <10 minutes.
*   **Parallelization:** Run lint, test, and build concurrently.
*   **Caching:**
    *   Cache dependencies (`node_modules`, Python venv).
    *   Cache build artifacts and Docker layers.

## 3. Quality Gates
| Gate | Tools | Action on Failure |
|---|---|---|
| Linting | ESLint, Ruff, Pylint | Block merge |
| Unit Tests | Jest, Pytest | Block merge |
| Security | npm audit, Bandit, Snyk | Block merge (high/critical) |
| Coverage | Istanbul, Coverage.py | Warn if below threshold |

## 4. CD: Deployment
*   **Immutable Artifacts:** Build once, deploy everywhere.
    *   Build Docker image -> Tag with commit SHA -> Push to registry.
*   **Zero Downtime:** Use rolling updates or blue-green deployments.
*   **Environment Parity:** Staging should mirror Production.

## 5. Example Workflow (GitHub Actions)
```yaml
version: 0.1.0
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci --cache .npm
      - run: npm run lint

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci --cache .npm
      - run: npm test

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - run: npm run build
```

## Guidelines
*   Keep pipelines simple and readable.
*   Fail fast: run fastest checks first.
*   Use secrets management for API keys (never hardcode).
