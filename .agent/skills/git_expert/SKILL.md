---
version: 1.1.0
name: git-expert
description: Use this skill for version control best practices. Covers branching,
  commit messages, PR conventions, worktree management, and conventional commit automation.
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# 🌿 Git Expert — Production-Grade Source Control

> **Philosophy:** Git history is a technical document, not a personal diary. Every commit should be a discrete, atomic improvement with a clear record of "why" and "what."

## 1. When to Use This Skill

- Creating new branches or managing worktrees
- Writing commit messages (Conventional Commits)
- Preparing Pull Requests or structured diffs
- Navigating complex git history (rebase, squash, cherry-pick)
- Resolving merge conflicts
- Organizing parallel development streams

## 2. Conventional Commits (Automation-Ready)

Always use the **Conventional Commits** specification for automated changelogs and versioning.

### Structure
`<type>[optional scope]: <description>`

### Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

### Example
```bash
feat(auth): add OIDC provider support for team-service
fix(ui): resolve clipping issue on mobile headers
docs: update competitive audit findings in README
```

## 3. Worktree Management (Context Switching)

Use `git worktree` to work on multiple branches simultaneously without affecting your main working directory. This is critical for high-velocity teams.

### Workflow
1. **Create**: `git worktree add ../feature-branch feature-branch`
2. **List**: `git worktree list`
3. **Remove**: `git worktree remove ../feature-branch`

**Rule:** Always keep worktrees outside the main project folder to avoid nested repository confusion.

## 4. Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready, stable code. |
| `develop` | Integration branch for features. |
| `feat/*` | Feature-specific development. |
| `fix/*` | Bug fixes for existing features. |
| `hotfix/*` | Critical production fixes. |

**Rule:** Never commit directly to `main`. Always use PRs with at least one review.

## 5. Atomic Commits & Rebasing

- **Atomic Commits**: One commit = one change. If you find yourself using "and" in the message, split the commit.
- **Clean History**: Use `git rebase -i` to squash "work-in-progress" commits before merging to `main`.
- **Force Push Safely**: Use `git push --force-with-lease` when updating PRs after a rebase.

## 6. PR Conventions

- **Title**: Use Conventional Commit format.
- **Description**: Linked issues, summary of changes, and verification evidence.
- **Screenshots/Videos**: Mandatory for UI changes.
- **Checklist**: Ensure tests pass, linter is clean, and docs are updated.

## Guidelines

- **Pull frequently.** Avoid long-lived branches that diverge heavily.
- **Verify before commit.** Run `skillsmith doctor` or local tests before `git commit`.
- **Ignore the noise.** Ensure `.gitignore` is comprehensive (use `git-expert` to review it).
- **Sign your commits.** Use GPG/SSH signatures for verified provenance.
