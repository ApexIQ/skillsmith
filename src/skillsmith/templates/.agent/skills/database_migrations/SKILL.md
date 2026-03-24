---
version: 0.1.0
name: database-migrations
description: Use this skill when modifying database schemas or running migrations. It defines safe patterns for SQLModel/Alembic.
tags: [database, sql, migrations, schema, alembic]
---

# 🗄️ Database & Migrations

> **Rule:** Never modify production schema without a migration. Never run migrations without a backup.

## 1. Schema Design (SQLModel)
*   **Nullable by Default:** New columns should be `Optional[T] = None` to avoid breaking existing rows.
*   **Indexes:** Add indexes to columns used in `WHERE` clauses (`index=True`).
*   **Foreign Keys:** Always define relationships explicitly.

```python
class Email(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    subject: str = Field(index=True)  # Indexed for search
    user_id: int = Field(foreign_key="user.id")  # FK defined
    archived_at: datetime | None = None  # Nullable for new column
```

## 2. Migration Strategy (Alembic)

### Safe Migrations
| Operation | Safe? | Notes |
|---|---|---|
| Add nullable column | ✅ | No data loss, backward compatible. |
| Add non-nullable column | ⚠️ | Needs default value OR multi-step migration. |
| Rename column | ❌ | Breaks existing queries. Use add/copy/drop. |
| Drop column | ⚠️ | Verify no code references it. |

### Multi-Step Migration (for risky changes)
1.  **Deploy 1:** Add new column (nullable).
2.  **Backfill:** Script to populate new column from old.
3.  **Deploy 2:** Make new column non-nullable, drop old column.

## 3. Running Migrations
```bash
# Generate migration
alembic revision --autogenerate -m "add archived_at column"

# Review the generated file!
# Then apply:
alembic upgrade head
```

## Examples
*   **Adding a feature flag column:** Add nullable, deploy, backfill, make non-nullable.

## Guidelines
*   Always backup before migrating production.
*   Test migrations on a copy of production data first.
*   Never use `DROP` in the same deploy as the code change.
