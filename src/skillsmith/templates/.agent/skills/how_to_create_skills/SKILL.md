---
version: 0.1.0
name: how-to-create-skills
description: Use this skill when creating new agentic skills. It defines the format, structure, and best practices for writing effective SKILL.md files.
---

# 📚 How to Create Skills

> **Philosophy:** Skills are reusable playbooks that ensure consistent, high-quality work.

## 1. File Structure
Every skill is a folder containing at minimum a `SKILL.md` file:

```
skills/
  my_new_skill/
    SKILL.md          # Required: Main instructions
    scripts/          # Optional: Helper scripts
    examples/         # Optional: Reference implementations
    templates/        # Optional: Starter files
```

## 2. SKILL.md Format

### Required: YAML Frontmatter
```yaml
---
version: 0.1.0
name: my-skill-name
description: A clear description of what this skill does and when to use it.
---
```

| Field | Purpose |
|---|---|
| `name` | Unique identifier (lowercase, hyphens). |
| `description` | Explains WHAT the skill does and WHEN to use it. This is critical for skill discovery. |

### Body Structure
```markdown
# Title with Emoji

> **Philosophy/Rule:** Core principle of this skill.

## 1. Section Name
Content with tables, examples, code blocks.

## Examples
*   **Good example:** Description.
*   **Bad example:** What to avoid.

## Guidelines
*   Key takeaway 1.
*   Key takeaway 2.
```

## 3. Best Practices

### Keep It Focused
*   **One skill = One purpose.** Don't create a "mega skill" that does everything.
*   If a skill exceeds 500 lines, split into multiple skills.

### Write for Discoverability
*   The `description` field is used to find relevant skills.
*   Be specific: "Use when writing FastAPI endpoints" not "Backend stuff".

### Include Concrete Examples
*   Show code that demonstrates the pattern.
*   Include both GOOD and BAD examples.

### Use Tables for Quick Reference
*   Tables are scannable and concise.
*   Great for checklists, patterns, and comparisons.

### Cross-Reference Other Skills
*   Link to related skills: "See `debugging` skill for troubleshooting."

## 4. Skill Creation Checklist
- [ ] Created folder in `skills/` directory.
- [ ] Added `SKILL.md` with YAML frontmatter.
- [ ] `description` clearly states WHAT and WHEN.
- [ ] Included at least one concrete example.
- [ ] Added guidelines section.
- [ ] Tested skill is discoverable and clear.

## Examples

**Good Skill Description:**
```yaml
description: Use this skill when creating REST API endpoints with FastAPI. Covers routing, validation, and error handling.
```

**Bad Skill Description:**
```yaml
description: FastAPI stuff.
```

## Guidelines
*   Skills should be portable - no project-specific paths.
*   Update skills when you discover better patterns.
*   Share useful skills with your team via version control.
