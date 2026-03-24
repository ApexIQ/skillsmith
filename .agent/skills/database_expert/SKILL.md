---
version: 1.0.0
name: database-expert
description: Use this skill when designing databases, writing queries, optimizing
  performance, or planning migrations. Covers SQL optimization, schema design, indexing
  strategies, PostgreSQL patterns, migration...
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# 🗄️ Database Expert — Production-Grade Database Engineering

> **Philosophy:** Your database is the foundation of your application. A bad schema is technical debt that compounds with every row inserted. Design it right, index it early, migrate it safely.

## 1. When to Use This Skill

- Designing database schemas for new features
- Optimizing slow queries
- Planning index strategies
- Writing and reviewing migrations
- Choosing between SQL and NoSQL
- Debugging database performance issues
- Planning data model changes for existing systems

## 2. Schema Design Principles

### Normalize First, Denormalize When Proven Necessary

```sql
-- GOOD: Normalized schema — single source of truth
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'member'
        CHECK (role IN ('member', 'admin', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE team_members (
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);

-- BAD: User data duplicated in every table that references them
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_name VARCHAR(100),  -- duplicated from users table
    user_email VARCHAR(255), -- will drift from source
    -- ...
);
```

### Use Proper Types

| Data | ❌ Bad Type | ✅ Good Type | Why |
|------|-----------|-------------|-----|
| Primary key | `INT AUTO_INCREMENT` | `UUID` | Distributed-safe, no enumeration attacks |
| Money | `FLOAT` | `NUMERIC(12,2)` | Float arithmetic is imprecise |
| Timestamps | `TIMESTAMP` | `TIMESTAMPTZ` | Always store with timezone |
| Status/enum | `VARCHAR` | `VARCHAR + CHECK` | Enforce valid values at DB level |
| JSON blobs | `TEXT` | `JSONB` (PostgreSQL) | Indexable, queryable, validated |
| Boolean | `INT(1)` | `BOOLEAN` | Semantic correctness |
| IP address | `VARCHAR(45)` | `INET` (PostgreSQL) | Built-in validation + operators |

## 3. Indexing Strategy

### When to Add Indexes

```sql
-- Rule: Index columns used in WHERE, JOIN, ORDER BY, and UNIQUE constraints

-- GOOD: Index on frequently filtered columns
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role) WHERE role = 'admin'; -- partial index

-- GOOD: Composite index for multi-column queries
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
-- Covers: WHERE user_id = ? AND status = ?
-- Also covers: WHERE user_id = ? (left prefix)
-- Does NOT cover: WHERE status = ? (need separate index)

-- GOOD: Covering index (avoids table lookup)
CREATE INDEX idx_users_list ON users(name, email, created_at);
-- Query: SELECT name, email, created_at FROM users ORDER BY name
-- → Index-only scan, never touches heap
```

### Index Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| Index every column | Index only columns in WHERE/JOIN/ORDER BY |
| Missing index on FK columns | Always index foreign key columns |
| `SELECT *` with covering index | Select only needed columns |
| Index on low-cardinality column | Partial index or skip (full scan is faster) |
| Too many indexes on write-heavy table | Balance read speed vs write overhead |

### How to Find Missing Indexes

```sql
-- PostgreSQL: Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;

-- PostgreSQL: Find sequential scans (missing indexes)
SELECT relname, seq_scan, seq_tup_read, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC;

-- EXPLAIN ANALYZE — always check query plans
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM users WHERE email = 'jane@test.com';
-- Look for: Seq Scan (bad) vs Index Scan (good)
```

## 4. Query Optimization

### The N+1 Problem

```python
# BAD: N+1 — 1 query for teams, then N queries for members
teams = db.query("SELECT * FROM teams")
for team in teams:
    team.members = db.query(
        "SELECT * FROM users JOIN team_members ON ... WHERE team_id = %s",
        team.id
    )  # This runs N times!

# GOOD: Single query with JOIN
teams_with_members = db.query("""
    SELECT t.*, u.name, u.email
    FROM teams t
    JOIN team_members tm ON t.id = tm.team_id
    JOIN users u ON tm.user_id = u.id
    ORDER BY t.name, u.name
""")
```

### Pagination

```sql
-- GOOD: Cursor-based pagination (fast, stable)
SELECT * FROM users
WHERE created_at < :last_created_at
ORDER BY created_at DESC
LIMIT 20;

-- OK for small datasets: Offset pagination
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 20 OFFSET 40;
-- ⚠️ Gets slower as offset increases — scans and discards rows

-- BAD: No pagination
SELECT * FROM users; -- 10M rows → OOM
```

### Bulk Operations

```sql
-- GOOD: Batch insert
INSERT INTO events (user_id, event_type, data)
VALUES
    ('u1', 'login', '{}'),
    ('u2', 'signup', '{}'),
    ('u3', 'purchase', '{"amount": 99.99}');

-- GOOD: Batch update with VALUES
UPDATE products AS p
SET price = v.new_price
FROM (VALUES
    ('p1', 29.99),
    ('p2', 49.99),
    ('p3', 99.99)
) AS v(id, new_price)
WHERE p.id = v.id;

-- BAD: Loop of individual inserts
for event in events:
    db.execute("INSERT INTO events ...", event)  # 1000 round-trips
```

## 5. Migration Safety

### Safe Migration Rules

| ✅ Safe | ❌ Dangerous |
|---------|-------------|
| `ADD COLUMN` (nullable) | `ADD COLUMN NOT NULL` without default |
| `CREATE INDEX CONCURRENTLY` | `CREATE INDEX` (locks table) |
| Add new table | Drop column with active readers |
| Add default value | Change column type |
| Rename via new column + backfill | `ALTER TABLE RENAME COLUMN` under traffic |

### Safe Column Addition Pattern

```sql
-- Step 1: Add nullable column (instant, no lock)
ALTER TABLE users ADD COLUMN phone VARCHAR(20);

-- Step 2: Backfill in batches (no full table lock)
UPDATE users SET phone = 'unknown'
WHERE phone IS NULL AND id IN (
    SELECT id FROM users WHERE phone IS NULL LIMIT 1000
);
-- Repeat until done

-- Step 3: Add NOT NULL constraint (after all rows backfilled)
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;

-- Step 4: Add default for future inserts
ALTER TABLE users ALTER COLUMN phone SET DEFAULT 'unknown';
```

### Safe Index Creation

```sql
-- GOOD: Concurrent index — no table lock
CREATE INDEX CONCURRENTLY idx_users_phone ON users(phone);

-- BAD: Standard index — locks entire table for writes
CREATE INDEX idx_users_phone ON users(phone);
```

## 6. PostgreSQL-Specific Power Features

```sql
-- JSONB indexing
CREATE INDEX idx_user_metadata ON users USING GIN (metadata);
SELECT * FROM users WHERE metadata @> '{"plan": "premium"}';

-- Full-text search
ALTER TABLE articles ADD COLUMN search_vector tsvector;
UPDATE articles SET search_vector = to_tsvector('english', title || ' ' || body);
CREATE INDEX idx_articles_fts ON articles USING GIN (search_vector);
SELECT * FROM articles WHERE search_vector @@ to_tsquery('english', 'database & optimization');

-- Row-level security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_documents ON documents
    FOR ALL TO app_user
    USING (owner_id = current_setting('app.current_user_id')::uuid);

-- Materialized views for expensive aggregations
CREATE MATERIALIZED VIEW daily_stats AS
SELECT date_trunc('day', created_at) AS day, COUNT(*) AS signups
FROM users GROUP BY 1;
-- Refresh on schedule: REFRESH MATERIALIZED VIEW CONCURRENTLY daily_stats;
```

## 7. SQL vs NoSQL Decision Matrix

| Factor | Choose SQL | Choose NoSQL |
|--------|-----------|-------------|
| Data relationships | Complex joins, foreign keys | Denormalized, nested documents |
| Consistency | ACID required | Eventual consistency OK |
| Schema | Known, stable schema | Schema evolves frequently |
| Query patterns | Complex ad-hoc queries | Key-value or document lookups |
| Scale | Vertical + read replicas | Horizontal sharding built-in |
| Transaction scope | Multi-table transactions | Single-document operations |

**Rule:** When in doubt, choose PostgreSQL. It handles 90% of use cases up to massive scale.

## Guidelines

- **PostgreSQL by default.** Unless you have a specific reason for something else.
- **Index foreign keys.** Every FK column needs an index — always.
- **EXPLAIN ANALYZE everything.** Never ship a query without checking its plan.
- **Migrations are one-way tickets.** Test them. Backup first. Use `CONCURRENTLY`.
- **Never `SELECT *` in production.** Select only the columns you need.
- **Paginate everything.** No unbounded queries. Ever.
- See `database-migrations` skill for migration workflow and safety patterns.
- See `security-audit` skill for SQL injection prevention.
