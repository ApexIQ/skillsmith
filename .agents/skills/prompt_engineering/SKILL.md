---
version: 0.1.0
name: prompt-engineering
description: Use this skill when crafting effective prompts for AI agents. Covers clarity, context, examples, and output formatting.
---

# ✍️ Prompt Engineering

> **Philosophy:** The quality of AI output is directly proportional to the quality of the prompt.

## Core Principles

### 1. Be Specific
```
❌ "Make this better"
✅ "Refactor this function to reduce cyclomatic complexity below 5, 
    extract helper functions for repeated logic, and add JSDoc comments"
```

### 2. Provide Context
```
❌ "Fix the bug"
✅ "The login endpoint returns 500 when email contains '+'. 
    We use FastAPI with Pydantic validation. Error is in auth/router.py"
```

### 3. Specify Output Format
```
❌ "Explain this code"
✅ "Explain this code in 3 bullet points:
    1. What it does
    2. Key dependencies
    3. Potential issues"
```

## Prompt Structure

Use clear sections for complex prompts:

```markdown
<context>
We're building a FastAPI backend with SQLModel ORM.
Current task: Add pagination to /users endpoint.
</context>

<instructions>
1. Add `skip` and `limit` query parameters
2. Default limit: 20, max limit: 100
3. Return total count in response headers
</instructions>

<constraints>
- Don't break existing tests
- Follow existing code patterns in routers/
</constraints>

<output_format>
Return only the modified code, no explanations.
</output_format>
```

## Prompting Techniques

| Technique | Use Case | Example |
|-----------|----------|---------|
| **Zero-shot** | Simple tasks | "Convert this to TypeScript" |
| **Few-shot** | Pattern learning | "Here are 2 examples... now do this" |
| **Chain-of-thought** | Complex reasoning | "Think step by step..." |
| **Role/Persona** | Specialized output | "You are a security auditor..." |

## Few-Shot Example

```markdown
Convert Python to SQL queries:

Example 1:
Python: `users.filter(age > 18)`
SQL: `SELECT * FROM users WHERE age > 18`

Example 2:
Python: `orders.filter(status="pending").count()`
SQL: `SELECT COUNT(*) FROM orders WHERE status = 'pending'`

Now convert:
Python: `products.filter(price < 100, in_stock=True).order_by("name")`
```

## Chain-of-Thought Example

```markdown
Analyze this code for security issues. Think step by step:

1. First, identify all user inputs
2. Then, trace how each input flows through the code
3. Check if inputs are validated/sanitized
4. Look for SQL injection, XSS, or auth bypass
5. Finally, list vulnerabilities with severity
```

## Anti-Patterns

| ❌ Don't | ✅ Do |
|---------|------|
| Vague instructions | Specific, measurable goals |
| Assume agent knows context | Provide relevant background |
| Ask "don't do X" | Ask "do Y instead" |
| Dump entire codebase | Provide focused, relevant snippets |
| Single mega-prompt | Break into focused sub-prompts |

## Guidelines

*   **Iterate:** Start simple, refine based on output.
*   **Test edge cases:** Include unusual inputs in examples.
*   **Match input/output length:** Short prompts → brief outputs.
*   **Use delimiters:** Triple backticks, XML tags for clarity.
*   **Version your prompts:** Track what works in documentation.
