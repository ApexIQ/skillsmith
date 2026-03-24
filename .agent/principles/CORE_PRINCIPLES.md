# Core Principles

> **Standard Operating Procedure**: These rules are immutable and must be applied to every tool execution.

## 1. Engineering Priorities
- **Testability**: testability
- **Maintainability**: maintainability
- **Verification**: verification
- **Automation**: automation

## 2. Security & Trust Policy
- **Remote Skills**: Blocked
- **GitHub Pins**: Required
- **Trust Score**: 65+ required
- **Verification Mode**: OPTIONAL

## 3. Behavioral Guardrails
- **Atomic Edits**: Never combine unrelated changes in a single file write.
- **Verification First**: Prove success with command output before claiming completion.
- **Minimalist Design**: Prefer the simplest code that satisfies the requirement.
- **No Placeholders**: Never use `// TODO` or `// implement later` in production-bound code.
