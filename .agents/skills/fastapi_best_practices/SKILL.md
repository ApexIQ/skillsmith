---
version: 0.1.0
name: fastapi-best-practices
description: Use this skill when creating or modifying Python backend services with FastAPI. It defines API design, security, and testing standards.
---

# ⚡ FastAPI Best Practices

## 1. Project Structure
*   **Modular Features:** Organize code by feature/domain, not by type.
    *   Each feature folder: `router.py`, `service.py`, `models.py`, `tests/`.
*   **No Global State:** Use Dependency Injection (`Depends`), not global variables.

## 2. API Design (RESTful URLs)
| Pattern | Example | Why |
|---|---|---|
| ✅ Resource-based | `GET /users/{id}` | Predictable, cacheable. |
| ❌ Verb-based | `GET /get_user_by_id` | Unclear, non-standard. |

*   **Pydantic Models:** Always use for Request/Response schemas.
    *   `CreateUserRequest` (Input), `UserResponse` (Output).
    *   **Never return ORM/DB objects directly from endpoints.**

## 3. Dependency Injection
```python
from fastapi import Depends

def get_current_user(token: str = Depends(oauth2_scheme)): ...
def get_db(session: Session = Depends(get_session)): ...

@router.get("/items/{item_id}")
def get_item(item_id: int, user = Depends(get_current_user), db = Depends(get_db)):
    ...
```

## 4. Error Handling
*   Use `HTTPException` with specific status codes (400, 401, 403, 404, 500).
*   Log errors *before* raising the exception for traceability.

## 5. Security (Critical)
*   **Ownership Verification:** ALWAYS check if resource belongs to user.
    ```python
    if item.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Not found") # Use 404, not 403
    ```
*   **Rate Limiting:** Apply on public/sensitive endpoints.

## Examples
*   **New endpoint:** Define Pydantic schema -> Add route -> Add ownership check -> Write test.

## Guidelines
*   Keep endpoints thin. Business logic goes in service layer.
*   Every new endpoint MUST have a corresponding test.
