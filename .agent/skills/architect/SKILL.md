---
version: 1.0.0
name: architect
description: Use this skill when making system design decisions. Covers architecture
  patterns, tradeoff analysis, scalability planning, component boundaries, data flow
  design, and technology selection.
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# 🏗️ Architect — System Design Decisions

> **Philosophy:** Architecture is the set of decisions you wish you could get right early. Every design choice is a tradeoff — name the tradeoff explicitly or you'll discover it in production.

## 1. When to Use This Skill

- Designing a new system or service from scratch
- Choosing between architectural patterns (monolith vs microservices, etc.)
- Making database or infrastructure decisions
- Defining API contracts and service boundaries
- Evaluating build-vs-buy decisions
- Scaling an existing system

## 2. The Architecture Decision Framework

### Step 1: Context Gathering

Before designing, answer these questions:

| Category | Questions |
|----------|-----------|
| **Users** | Who uses this? How many concurrent? Growth rate? |
| **Data** | How much data? Read-heavy or write-heavy? Consistency requirements? |
| **Reliability** | What's the cost of downtime? Required uptime SLA? |
| **Team** | How many engineers? What expertise exists? |
| **Timeline** | MVP deadline? When does it need to scale? |
| **Budget** | Cloud spend constraints? Licensing constraints? |

### Step 2: Architecture Decision Record (ADR)

For every significant decision, write an ADR:

```markdown
# ADR-001: Use PostgreSQL over MongoDB for User Data

## Status: Accepted
## Date: 2026-03-25

## Context
We need a database for user data with complex relationships (users → teams → projects → permissions). Expected scale: 100K users in Year 1, 1M in Year 3.

## Decision
Use PostgreSQL with row-level security.

## Tradeoffs Considered
| Option | Pros | Cons |
|--------|------|------|
| PostgreSQL | ACID, relations, mature, RLS | Horizontal scaling harder |
| MongoDB | Flexible schema, easy horizontal | No joins, consistency tradeoffs |
| DynamoDB | Infinite scale, serverless | Vendor lock-in, complex queries expensive |

## Consequences
- ✅ Strong consistency guarantees for permission checks
- ✅ Team has PostgreSQL experience
- ⚠️ Will need read replicas at ~500K users
- ⚠️ Schema migrations require coordination

## Review Date: 2026-09-25
```

### Step 3: Component Boundary Design

Define clear boundaries using this template:

```
┌─────────────────────────────────────────────────┐
│                   API Gateway                    │
│              (Auth, Rate Limit, CORS)            │
└──────┬──────────────┬──────────────┬────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────────┐
│ User Service│ │ Task Service│ │ Notification │
│             │ │             │ │ Service      │
│ Owns:       │ │ Owns:       │ │ Owns:        │
│ - users     │ │ - tasks     │ │ - templates  │
│ - teams     │ │ - workflows │ │ - channels   │
│ - perms     │ │ - history   │ │ - delivery   │
└──────┬──────┘ └─────┬──────┘ └──────────────┘
       │              │
       └──────┬───────┘
       ┌──────▼──────┐
       │  PostgreSQL  │
       │  (shared DB  │
       │   for now)   │
       └─────────────┘
```

**Boundary rules:**
- Each service owns its data — no direct DB access across boundaries
- Services communicate via API contracts (REST/gRPC), not shared state
- Start with a shared DB, split when scaling demands it (pragmatic monolith)
- Define ownership: every table, queue, and endpoint has exactly one owner

### Step 4: Data Flow Design

Map how data moves through the system:

```markdown
## Data Flow: User Creates a Task

1. Client → POST /api/tasks (JSON body)
2. API Gateway → Validates JWT, extracts user_id
3. Task Service → Validates input, creates task record
4. Task Service → Publishes "task.created" event
5. Notification Service → Consumes event, sends email/push
6. Task Service → Returns 201 with task object

## Data Flow: Failure Scenarios
- Step 2 fails (invalid JWT) → 401 Unauthorized
- Step 3 fails (validation) → 400 Bad Request with field errors
- Step 5 fails (email service down) → Task still created, notification retried via dead letter queue
```

### Step 5: Scalability Strategy

| Scale Stage | Users | Architecture | Key Changes |
|-------------|-------|-------------|-------------|
| Stage 1 | 0-10K | Monolith + PostgreSQL | Single server, vertical scaling |
| Stage 2 | 10K-100K | Monolith + Read Replicas + Redis | Add caching, read replicas, CDN |
| Stage 3 | 100K-1M | Service extraction + Queue | Extract hot services, add message queue |
| Stage 4 | 1M+ | Microservices + Kubernetes | Full service mesh, horizontal scaling |

**Rule:** Don't build Stage 4 architecture for Stage 1 traffic. Premature optimization is the root of all evil — but have a plan for when you'll need it.

## 3. Common Architecture Patterns

| Pattern | When to Use | When to Avoid |
|---------|------------|---------------|
| **Monolith** | < 5 engineers, < 100K users, fast iteration needed | Large team, independent deployment needed |
| **Modular Monolith** | 5-15 engineers, clear domain boundaries | Truly independent scaling requirements |
| **Microservices** | > 15 engineers, independent scaling, diverse tech stacks | Small team, early-stage product |
| **Event-Driven** | Async workflows, audit trails, decoupled services | Simple CRUD apps, strong consistency required |
| **CQRS** | Read/write patterns differ dramatically | Simple data models, small scale |
| **Serverless** | Spiky traffic, event processing, cost optimization | Consistent high traffic, complex state |

## 4. Technology Selection Matrix

When choosing technologies, score them:

| Criterion | Weight | Option A | Option B | Option C |
|-----------|--------|----------|----------|----------|
| Team expertise | 25% | 8/10 | 5/10 | 3/10 |
| Community/ecosystem | 20% | 9/10 | 7/10 | 6/10 |
| Performance fit | 20% | 7/10 | 9/10 | 8/10 |
| Operational cost | 15% | 6/10 | 8/10 | 9/10 |
| Hiring pool | 10% | 9/10 | 6/10 | 4/10 |
| Lock-in risk | 10% | 8/10 | 5/10 | 3/10 |
| **Weighted Score** | | **7.65** | **6.80** | **5.85** |

**Rule:** The best technology is the one your team can ship with this quarter.

## 5. Architecture Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| Microservices on day one | Start monolith, extract when needed |
| No ADRs — decisions in Slack | Write ADRs, review them, version them |
| "We might need this" (speculative) | Build for today's requirements, plan for tomorrow's |
| Shared mutable state between services | Each service owns its data exclusively |
| Choosing tech you want to learn | Choose tech the team already knows |
| No failure mode design | Design for failure first, happy path second |

## Guidelines

- **Every architecture decision gets an ADR.** If it's worth debating, it's worth documenting.
- **Design for failure.** Ask "what happens when X is down?" for every component.
- **Optimize for team velocity.** The best architecture is the one your team can debug at 2 AM.
- **Review architecture decisions quarterly.** Context changes — decisions should too.
- See `planner` skill for breaking designs into implementation tasks.
- See `software-architecture` skill for broader architectural principles.
