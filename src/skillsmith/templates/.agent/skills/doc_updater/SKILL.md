---
version: 1.0.0
name: doc-updater
description: Use this skill when documentation needs to be synced with code changes. Covers README updates, API docs, inline comments, changelogs, and ensuring docs stay accurate after refactors.
---

# 📝 Doc Updater — Keep Documentation Alive

> **Philosophy:** Stale docs are worse than no docs. Every code change that affects behavior must update the corresponding documentation in the same PR.

## 1. When to Use This Skill

- After modifying public APIs or CLI commands
- After adding/removing features
- After refactoring that changes file structure or module boundaries
- Before releasing a new version
- When onboarding docs don't match reality

## 2. The Documentation Sync Checklist

After ANY code change, check these in order:

### Tier 1: Must Update (Same PR)
- [ ] **README.md** — Does the quick start still work? Are commands/examples still valid?
- [ ] **API docs** — Did function signatures, parameters, or return types change?
- [ ] **CLI help text** — Did command names, flags, or descriptions change?
- [ ] **Inline comments** — Do comments near changed code still describe truth?
- [ ] **Error messages** — Do error messages reference correct commands/paths?

### Tier 2: Should Update (Within Sprint)
- [ ] **CHANGELOG.md** — Is the change logged under the correct version?
- [ ] **Architecture docs** — Did component boundaries or data flow change?
- [ ] **Configuration docs** — Did config options, defaults, or env vars change?
- [ ] **Migration guides** — Is there a breaking change that needs a migration path?

### Tier 3: Nice to Update (Backlog)
- [ ] **Tutorials/guides** — Do step-by-step guides still produce correct results?
- [ ] **FAQ** — Are answered questions still accurate?
- [ ] **Diagrams** — Do architecture diagrams reflect current state?

## 3. Documentation Patterns

### Pattern 1: Command Reference Sync

When CLI commands change, update docs systematically:

```bash
# Step 1: Generate current command surface
skillsmith --help > /tmp/commands.txt

# Step 2: Compare with documented commands in README
grep -E "^- \`skillsmith" README.md > /tmp/documented.txt

# Step 3: Diff to find drift
diff /tmp/commands.txt /tmp/documented.txt
```

### Pattern 2: API Documentation from Code

```python
# GOOD: Docstring IS the documentation
def create_user(name: str, email: str, role: str = "member") -> User:
    """Create a new user account.
    
    Args:
        name: Full name of the user (2-100 chars).
        email: Valid email address. Must be unique.
        role: User role. One of: "member", "admin", "viewer".
              Defaults to "member".
    
    Returns:
        User: The created user object with generated ID.
    
    Raises:
        ValidationError: If name or email is invalid.
        DuplicateError: If email already exists.
    
    Example:
        >>> user = create_user("Jane Doe", "jane@example.com")
        >>> user.id
        'usr_abc123'
    """
```

```python
# BAD: Docstring lies about the code
def create_user(name, email, role="member"):
    """Create a user."""  # Missing: args, returns, raises, examples
```

### Pattern 3: Changelog Entry

```markdown
## [0.7.0] - 2026-03-25

### Added
- `skillsmith evolve` command with FIX, DERIVE, and CAPTURE modes
- Skill quality metrics tracking in `skills.lock.json`
- Version DAG lineage for evolved skills

### Changed
- `skillsmith compose` now accepts `--learn` flag for post-execution analysis
- Default readiness gate now includes skill health check

### Deprecated
- `skillsmith update` will be renamed to `skillsmith upgrade` in v0.8.0

### Removed
- Nothing

### Fixed
- README command parity for `roles` command (#142)
- Profile inference for monorepo projects (#138)

### Security
- Updated `requests` to 2.32.0 to fix CVE-2026-XXXX
```

### Pattern 4: Breaking Change Migration Guide

```markdown
## Migration Guide: v0.6 → v0.7

### Breaking Change: `compose` output format

**Before (v0.6):**
```json
{"steps": ["Step 1", "Step 2"]}
```

**After (v0.7):**
```json
{"stages": [{"name": "discover", "steps": ["Step 1"]}, {"name": "build", "steps": ["Step 2"]}]}
```

**How to migrate:**
1. If you parse `compose --json` output, update your parser to read `stages[].steps` instead of `steps[]`
2. The legacy `steps` field is still emitted for backward compatibility but will be removed in v0.8
```

## 4. Automated Doc Checks

### CI Gate: Doc Freshness

```yaml
# In your CI pipeline
- name: Check doc freshness
  run: |
    # Fail if code changed but docs didn't
    CODE_CHANGED=$(git diff --name-only HEAD~1 | grep -c "src/")
    DOCS_CHANGED=$(git diff --name-only HEAD~1 | grep -c -E "(README|docs/|CHANGELOG)")
    if [ "$CODE_CHANGED" -gt 0 ] && [ "$DOCS_CHANGED" -eq 0 ]; then
      echo "⚠️ Code changed but no docs updated. Please check if docs need updating."
    fi
```

### Doc Link Checker

```bash
# Find broken internal links in markdown
grep -roh '\[.*\]([^)]*\.md)' docs/ | \
  sed 's/.*](//' | sed 's/)//' | \
  while read link; do
    [ ! -f "docs/$link" ] && echo "BROKEN: $link"
  done
```

## 5. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| "I'll update docs later" | Update docs IN the same PR as the code change |
| Copy-pasting code into docs | Reference code via links, auto-generate where possible |
| Docs describe implementation details | Docs describe behavior and intent, not internals |
| No examples in API docs | Every public function needs at least one example |
| Manually maintaining command lists | Auto-generate from `--help` output in CI |
| Version numbers hardcoded in prose | Use variables or auto-replace in build process |

## Guidelines

- **Same PR rule:** If your code PR changes behavior, docs update goes in the same PR.
- **Write for the reader, not yourself.** Assume the reader doesn't know your codebase.
- **Examples over explanations.** A good example teaches more than a paragraph.
- **Test your docs.** Copy-paste your quickstart commands — do they actually work?
- **Link, don't duplicate.** Reference the canonical source instead of copying content.
- See `planner` skill for including doc tasks in implementation plans.
