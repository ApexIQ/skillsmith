---
version: 0.1.0
name: backend-testing
description: Use this skill when writing tests for Python backend services. It covers unit, integration, and security testing standards.
tags: [testing, backend, python, pytest, unit]
---

# 🧪 Backend Testing Standards

> **Philosophy:** Untested code is broken code.

## 1. The Testing Pyramid
| Type | Coverage | Speed | Purpose |
|---|---|---|---|
| Unit | 70% | ⚡ Fast | Test individual functions/classes. |
| Integration | 20% | 🐢 Medium | Test API endpoints + Database. |
| E2E | 10% | 🐌 Slow | Full flows (Login -> Dashboard). |

## 2. Tooling
*   **Runner:** `pytest`.
*   **Fixtures:** Use `conftest.py` for shared setup (DB sessions, users).
*   **Mocking:** `unittest.mock` or `pytest-mock` for external APIs.

## 3. Rules of Engagement

### Rule 1: Isolation
Every test gets a fresh DB transaction that is rolled back after the test.

### Rule 2: Scoping (Critical for Security)
Always create 2 users (`user_a`, `user_b`). Ensure A cannot access B's data.
```python
def test_user_cannot_access_other_users_item(client, user_a_auth, user_b_item):
    response = client.get(f"/items/{user_b_item.id}", headers=user_a_auth)
    assert response.status_code == 404  # Must be 404, not 403
```

### Rule 3: Deterministic Data
*   Do not assume `ID=1`. Use the object's `.id` after creation.
*   Use fixed dates (e.g., `datetime(2026, 1, 1)`) in tests.

## Examples
*   **Testing a new endpoint:** Create fixtures -> Call endpoint -> Assert response + DB state.

## Guidelines
*   Run tests before every commit.
*   If a bug is found, write a failing test *first* before fixing.
