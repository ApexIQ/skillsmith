# 🧠 skills-agent

[![PyPI version](https://img.shields.io/pypi/v/skills-agent-lib.svg)](https://pypi.org/project/skills-agent-lib/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Portable agentic skills library for professional AI engineering.**

`skills-agent` is a CLI tool that scaffolds industry-standard `.agents` structures into any project. It imbues your AI coding assistants with project-agnostic "expertise" across the entire software lifecycle.

---

## 🚀 Quick Start

Initialize a new project with best-practice agent context in seconds:

```bash
# Install the library
pip install skills-agent-lib

# Scaffold the .agents structure and AGENTS.md
skills-agent init
```

---

## ✨ Key Features

- **23 Specialized Skills**: Out-of-the-box expertise for TDD, Security Audits, Context Engineering, and more.
- **AGENTS.md Standard**: Native support for the [agents.md](https://agents.md) open standard ("README for Agents").
- **Agentic Workflows**: Pre-defined templates for agentic loops, sub-agent coordination, and memory management.
- **Project Structure**: Scaffolds dedicated folders for `guides/`, `plans/`, and `workflows/`.
- **Portable & Modular**: Add only the skills you need for your specific tech stack.

---

## 🛠 Included Skills

Run `skills-agent list` to see all 23 available skills. Highlights include:

| Category | Skill | Description |
|----------|-------|-------------|
| **AI Strategy** | `memory-patterns` | Manage agent context window and long-term memory. |
| | `prompt-engineering` | Best practices for few-shot and chain-of-thought prompts. |
| | `agentic-workflow` | Implements the Anthropic Agentic Loop (Gather → Act → Verify). |
| **Engineering** | `test-driven-development` | Structured TDD (Red → Green → Refactor) for agents. |
| | `security-audit` | OWASP-based security checklists for automated reviews. |
| | `git-workflow` | Conventional commits and branching strategies. |
| **Fullstack** | `fastapi-best-practices` | Patterns for high-performance Python backends. |
| | `frontend-best-practices` | Modern React/Vite/Tailwind patterns. |

---

## 📖 Directory Structure

When you run `skills-agent init`, it creates:

```text
.
├── AGENTS.md           # High-level context for AI agents
└── .agents/
    ├── skills/         # Modular expertise (SKILL.md files)
    ├── guides/         # Project-specific style & architecture docs
    ├── plans/          # Active implementation plans and RFCs
    ├── workflows/      # Automated tasks and deployment templates
    ├── prd.md          # Standard blueprint for new features
    └── status.md       # Global project state tracker
```

---

## 💻 CLI Commands

### Initialize Project
Scaffold the full structure including all 23 skills.
```bash
skills-agent init
```

### Minimal Scaffolding
Create the directory structure and templates without the pre-built skills.
```bash
skills-agent init --minimal
```

### List Available Skills
View the library of portable expertise.
```bash
skills-agent list
```

### Add a Specific Skill
Add a single skill to an existing project.
```bash
skills-agent add memory-patterns
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🤝 Contributing

Contributions are welcome! If you have a portable skill that could benefit other developers, please open a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingSkill`)
3. Commit your Changes (`git commit -m 'feat: add AmazingSkill'`)
4. Push to the Branch (`git push origin feature/AmazingSkill`)
5. Open a Pull Request

---

Developed with ❤️ by **ApexIQ**
