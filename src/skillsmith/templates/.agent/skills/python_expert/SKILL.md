---
version: 1.0.0
name: python-expert
description: Use this skill when writing or reviewing Python code. Covers modern Python idioms (3.10+), type hints, project structure, packaging, performance patterns, async/await, error handling, and production-grade coding standards.
---

# 🐍 Python Expert — Production-Grade Python

> **Philosophy:** Python's simplicity is its power. Write code that reads like well-edited prose — explicit, flat, and simple. If your code needs a comment to explain what it does, rewrite the code.

## 1. When to Use This Skill

- Writing new Python modules, packages, or scripts
- Reviewing Python code for idioms and best practices
- Structuring Python projects for packaging and distribution
- Optimizing Python performance
- Writing async Python code
- Debugging Python-specific issues

## 2. Modern Python Idioms (3.10+)

### Type Hints — Always

```python
# GOOD: Fully typed
def fetch_users(
    team_id: str,
    active_only: bool = True,
    limit: int = 100,
) -> list[User]:
    """Fetch users for a team."""
    ...

# BAD: No types — impossible to maintain
def fetch_users(team_id, active_only=True, limit=100):
    ...
```

### Structural Pattern Matching (3.10+)

```python
# GOOD: Pattern matching for complex dispatch
match command:
    case {"action": "create", "data": data}:
        return create_item(data)
    case {"action": "delete", "id": item_id}:
        return delete_item(item_id)
    case {"action": action}:
        raise ValueError(f"Unknown action: {action}")
    case _:
        raise ValueError("Invalid command format")
```

### Dataclasses & Pydantic Over Raw Dicts

```python
# GOOD: Typed, validated, documented
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    id: str
    name: str
    email: str
    role: str = "member"
    created_at: datetime = field(default_factory=datetime.now)

# BETTER for APIs: Pydantic with validation
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    role: str = Field(default="member", pattern="^(member|admin|viewer)$")

# BAD: Raw dict — no validation, no docs, typo-prone
user = {"name": "Jane", "emial": "jane@test.com"}  # typo? who knows
```

### Context Managers for Resource Cleanup

```python
# GOOD: Resources always cleaned up
from contextlib import contextmanager

@contextmanager
def database_transaction(db):
    tx = db.begin()
    try:
        yield tx
        tx.commit()
    except Exception:
        tx.rollback()
        raise

with database_transaction(db) as tx:
    tx.execute("INSERT INTO users ...")
```

### Pathlib Over os.path

```python
# GOOD: Pathlib — readable, cross-platform
from pathlib import Path

config_dir = Path.home() / ".config" / "myapp"
config_dir.mkdir(parents=True, exist_ok=True)
config_file = config_dir / "settings.json"
data = json.loads(config_file.read_text())

# BAD: os.path — verbose, error-prone
import os
config_dir = os.path.join(os.path.expanduser("~"), ".config", "myapp")
os.makedirs(config_dir, exist_ok=True)
config_file = os.path.join(config_dir, "settings.json")
with open(config_file) as f:
    data = json.load(f)
```

## 3. Project Structure

```
my-project/
├── src/
│   └── my_package/
│       ├── __init__.py        # Public API exports
│       ├── __main__.py        # python -m my_package
│       ├── cli.py             # CLI entry point
│       ├── core/              # Business logic
│       │   ├── __init__.py
│       │   ├── models.py      # Data models
│       │   └── services.py    # Business operations
│       ├── api/               # HTTP layer (if applicable)
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   └── middleware.py
│       └── utils/             # Shared utilities
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures
│   ├── test_models.py
│   └── test_services.py
├── pyproject.toml             # Package config (NOT setup.py)
├── README.md
└── uv.lock                   # or requirements.txt
```

**Rules:**
- Use `src/` layout to prevent import shadowing
- Use `pyproject.toml`, never `setup.py` (PEP 621)
- Every `__init__.py` should explicitly export public APIs
- Tests mirror source structure

## 4. Error Handling

```python
# GOOD: Specific exceptions with context
class UserNotFoundError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")

class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation failed for '{field}': {message}")

# GOOD: Catch specific, re-raise with context
try:
    user = db.get_user(user_id)
except DatabaseError as e:
    raise UserNotFoundError(user_id) from e

# BAD: Catch-all that hides bugs
try:
    result = do_risky_thing()
except Exception:
    pass  # Swallowed — you'll never know what went wrong

# BAD: Bare except
try:
    result = do_risky_thing()
except:  # Catches KeyboardInterrupt, SystemExit — NEVER do this
    pass
```

## 5. Performance Patterns

| Pattern | Use When | Example |
|---------|----------|---------|
| **Generator** | Processing large sequences | `(x for x in big_list if x > 0)` |
| **`__slots__`** | Many instances of same class | `__slots__ = ('name', 'age')` |
| **`lru_cache`** | Pure function called with same args | `@lru_cache(maxsize=128)` |
| **`collections.defaultdict`** | Grouping/counting | `defaultdict(list)` |
| **`itertools`** | Complex iteration | `chain, groupby, islice` |
| **`str.join`** | String concatenation in loops | `' '.join(words)` not `s += word` |

```python
# GOOD: Generator for memory efficiency
def read_large_file(path: Path):
    with path.open() as f:
        for line in f:
            yield line.strip()

# Process 10GB file with constant memory
for line in read_large_file(Path("huge.log")):
    process(line)
```

## 6. Async Python

```python
# GOOD: Async for I/O-bound work
import asyncio
import httpx

async def fetch_all_users(user_ids: list[str]) -> list[User]:
    async with httpx.AsyncClient() as client:
        tasks = [fetch_user(client, uid) for uid in user_ids]
        return await asyncio.gather(*tasks)

async def fetch_user(client: httpx.AsyncClient, user_id: str) -> User:
    response = await client.get(f"/api/users/{user_id}")
    response.raise_for_status()
    return User(**response.json())

# BAD: Sync requests in a loop (100 requests = 100x latency)
def fetch_all_users_slow(user_ids):
    results = []
    for uid in user_ids:
        response = requests.get(f"/api/users/{uid}")  # blocks
        results.append(response.json())
    return results
```

**Rule:** Use async for I/O-bound work (HTTP, DB, files). Use multiprocessing for CPU-bound work. Threading is almost never the right answer in Python.

## 7. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| Mutable default args `def f(x=[])` | Use `None` sentinel: `def f(x=None)` |
| `from module import *` | Explicit imports: `from module import thing` |
| Bare `except:` | Catch specific: `except ValueError:` |
| String concatenation in loops | `''.join(parts)` |
| `type(x) == str` | `isinstance(x, str)` |
| Hand-rolling JSON serialization | Use Pydantic or dataclass + `json` |
| Nested try/except 4 levels deep | Refactor into smaller functions |
| Global mutable state | Dependency injection or context vars |

## Guidelines

- **Type everything.** Use `mypy --strict` or `pyright` in CI.
- **Format with `ruff`.** Zero-config, fast, replaces black + isort + flake8.
- **Use `uv` for packages.** 10-100× faster than pip for dependency resolution.
- **Prefer composition over inheritance.** Python's duck typing makes composition natural.
- **Write docstrings for public APIs.** Google style with Args/Returns/Raises.
- **Test with `pytest`.** Fixtures, parametrize, and plugins make testing pleasant.
- See `fastapi-best-practices` skill for API-specific Python patterns.
- See `testing-backend-best-practices` skill for Python testing strategies.
