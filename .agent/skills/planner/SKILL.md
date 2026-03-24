---
version: 1.0.0
name: planner
description: Use this skill when planning feature implementations. Covers requirements
  decomposition, acceptance criteria, task sequencing, risk identification, and creating
  executable implementation plans befo...
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# 📋 Planner — Feature Implementation Planning

> **Philosophy:** The best code is the code you plan before you write. Every feature needs a clear plan with measurable acceptance criteria before the first line is written.

## 1. When to Use This Skill

- Starting a new feature or user story
- Breaking down a large task into subtasks
- Creating sprint/iteration plans
- Writing technical design documents
- Estimating effort and identifying risks

## 2. The Planning Framework

### Step 1: Problem Definition
Before planning solutions, nail the problem:

| Question | Example Answer |
|----------|---------------|
| What problem does this solve? | Users can't reset passwords without support |
| Who is affected? | All 12K active users |
| What does success look like? | Self-service password reset in < 2 minutes |
| What are the constraints? | Must work with existing OAuth provider |
| What's the deadline? | Sprint 14 (2 weeks) |

### Step 2: Requirements Decomposition

Break the feature into atomic units:

```markdown
## Feature: Self-Service Password Reset

### Functional Requirements
1. FR-1: User can request a password reset via email
   - Acceptance: Email sent within 30s of request
   - Edge case: Invalid email returns generic "if account exists" message
   
2. FR-2: Reset link expires after 1 hour
   - Acceptance: Expired links show clear error with re-request option
   - Edge case: Multiple requests invalidate previous links

3. FR-3: New password must meet security policy
   - Acceptance: Real-time validation feedback on password strength
   - Edge case: Password same as last 5 passwords is rejected

### Non-Functional Requirements
- NFR-1: Reset flow completes in < 2 minutes end-to-end
- NFR-2: Rate-limited to 5 requests per email per hour
- NFR-3: All reset events logged for security audit
```

### Step 3: Task Sequencing

Order tasks by dependency, not importance:

```markdown
## Implementation Plan

### Phase 1: Backend Foundation (Day 1-2)
- [ ] T1: Create password_reset table migration
- [ ] T2: Implement token generation service
- [ ] T3: Implement email sending service
- [ ] T4: Create POST /api/auth/reset-request endpoint
- [ ] T5: Create POST /api/auth/reset-confirm endpoint

### Phase 2: Frontend (Day 3-4)
- [ ] T6: Create ResetRequestForm component
- [ ] T7: Create ResetConfirmForm component
- [ ] T8: Add password strength indicator
- [ ] T9: Wire up API calls and error handling

### Phase 3: Testing & Polish (Day 5)
- [ ] T10: Write unit tests for token service
- [ ] T11: Write integration tests for reset flow
- [ ] T12: Write E2E test for happy path
- [ ] T13: Security review of token handling
```

### Step 4: Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Email delivery delays | Medium | High | Add retry queue, show "check spam" message |
| Token collision | Low | Critical | Use UUID v4 + timestamp, add uniqueness constraint |
| Rate limiting bypass | Medium | High | Implement at API gateway level, not just app |
| Scope creep (SSO, MFA) | High | Medium | Defer to Phase 2, document in backlog |

### Step 5: Acceptance Criteria Matrix

Write acceptance criteria that are **testable and binary** (pass/fail):

```markdown
## Done Criteria

### Must Pass (Blocking)
- [ ] User receives reset email within 30 seconds
- [ ] Expired tokens are rejected with helpful message
- [ ] Password validation enforces minimum 8 chars + 1 special
- [ ] Rate limiting blocks after 5 requests/hour
- [ ] All endpoints have unit + integration tests
- [ ] No secrets in codebase (no hardcoded keys)

### Should Pass (Non-blocking)
- [ ] Password strength meter shows real-time feedback
- [ ] Success/error states have proper animations
- [ ] Mobile-responsive reset forms
```

## 3. Planning Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| "Build the auth system" (vague) | Break into 13 specific, testable tasks |
| Estimating without decomposition | Estimate each subtask, sum with buffer |
| Planning in your head | Write it down — if it's not written, it doesn't exist |
| Planning the entire product at once | Plan only the next iteration in detail |
| No risk identification | Every plan needs at least 3 identified risks |
| Acceptance criteria like "it works" | Binary, testable criteria with edge cases |

## 4. Templates

### Quick Plan (< 1 day feature)
```markdown
## Feature: [Name]
**Problem:** [1 sentence]
**Solution:** [1 sentence]
**Tasks:**
1. [ ] [Task with acceptance criteria]
2. [ ] [Task with acceptance criteria]
3. [ ] [Test task]
**Risks:** [At least 1]
**Done when:** [Binary criteria]
```

### Full Plan (Multi-day feature)
Use the 5-step framework above with all sections.

## Guidelines

- **Plan granularity matches risk.** Low-risk bug fix = quick plan. New auth system = full plan.
- **Every task must be completable in < 4 hours.** If not, decompose further.
- **Plans are living documents.** Update them as you learn, don't treat them as contracts.
- **Include "not doing" section.** Explicitly state what's deferred to prevent scope creep.
- See `how-to-create-implementation-plan` skill for RFC-style technical design docs.
- See `architect` skill for system design decisions within your plan.
