<div align="center">

<img src="skillsmith_hero_banner_1774380976071.png" width="100%" alt="Skillsmith Hero Banner">

# ⚡ Skillsmith
### The Operating System for AI Coding Agents

[![PyPI version](https://img.shields.io/pypi/v/skillsmith.svg?color=blue)](https://pypi.org/project/skillsmith/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/ApexIQ/skillsmith?style=social)](https://github.com/ApexIQ/skillsmith)

**Standardize, Compose, and Scale your AI-Assisted Engineering.**

[Overview](#-overview) • [Quick Start](#-quick-start) • [Supported Tools](#-supported-tools) • [The Skills Catalog](#-the-skills-catalog) • [Pillars](#-three-pillars-to-scale)

</div>

---

## 🚀 Overview

**Skillsmith** is the infrastructure layer every developer needs before their first AI-assisted commit. It bridges the gap between raw LLMs and professional codebase execution by turning static project instructions into dynamic, profile-driven **Skills-as-Code**.

While tools like Claude Code and Cursor offer great interfaces, **Skillsmith** provides the *intelligence backbone* that makes them 10x more effective through structured roles, deterministic workflows, and rigorous readiness gates.

### Why Skillsmith?
*   **Trust X Evolution X Content**: Native support for trust-verified publisher keys and self-evolving skills.
*   **Multi-Agent Orchestration**: Standardize instructions across Claude, Cursor, Windsurf, Zencoder, and more.
*   **33+ Power Workflows**: Instant access to `/refactor`, `/audit`, `/debug`, `/tdd`, and `/deploy-checklist`.
*   **Zero Drift**: Use `skillsmith doctor` to keep your AI rules 100% aligned with your code.

---

## 🛠 Supported Tools

Skillsmith manages rule-sets and workflow surfaces for the entire AI engineering ecosystem:

| Platform | Surface Type | Management Path |
|----------|--------------|-----------------|
| **Claude Code** | Slash Commands | `.claude/commands/*.md` |
| **Cursor** | MDC Rules | `.cursor/rules/*.mdc` |
| **Windsurf** | Global Rules | `.windsurf/rules/skillsmith.md` |
| **Zencoder** | Agent Instructions | `.zencoder/rules/*.md` |
| **GitHub Copilot** | Custom Instructions | `.github/copilot-instructions.md` |
| **Custom Agents** | Unified Context | `AGENTS.md` & `GEMINI.md` |

---

## 🏁 Quick Start

### 1. Install
```bash
pip install skillsmith
```

### 2. Initialize (The "Guided" Path)
```bash
skillsmith init --guided
```
*Skillsmith will scan your repo, infer your tech stack, and recommend a starter skill-set.*

### 3. Align & Verify
```bash
skillsmith align
skillsmith doctor
```

### 4. Compose a Workflow
```bash
skillsmith compose "Implement a robust JWT authentication system"
```
*Creates a detailed, stage-based runbook in `.agent/workflows/` for your AI agent to follow.*

---

## 📚 The Skills Catalog

Skillsmith ships with **36+ production-grade skills** ready to be injected into your agents:

*   **Personas**: `orchestrator`, `researcher`, `implementer`, `reviewer`.
*   **Specialists**: `planner`, `architect`, `build-resolver`, `security-reviewer`.
*   **Experts**: `python-expert`, `typescript-expert`, `go-expert`, `database-expert`.
*   **Workflows**: `test-changes`, `deploy-checklist`, `migration-planner`.

Run `skillsmith check` to see your installed skills or `skillsmith recommend` to see what's missing.

---

## 🏛 Three Pillars to Scale

1.  **Content Gravity**: 60+ production-grade skills and 15+ subagent personas.
2.  **Self-Evolution Engine**: Skills that auto-fix, auto-improve, and auto-learn from execution logs.
3.  **Team Intelligence**: Shared skill registries and CI readiness gates to standardize agent behavior across Orgs.

---

## 🤖 Commands for AI Agents

Once Skillsmith is initialized, your AI agents gain access to a powerful command surface:

- `/plan` — Multi-stage implementation planning with acceptance criteria.
- `/audit` — Full project integrity, security, and drift audit.
- `/refactor` — Strategic refactoring with automated verification.
- `/ready` — High-speed pre-release sanity check.
- `/sync` — Refresh project context and re-render all instructions.

---

## 📈 Roadmap

We are currently moving towards **Pillar 2: The Evolution Engine**, enabling skills to learn from every successful task completion. Check our [ROADMAP.md](.agent/ROADMAP.md) for more details.

---

## 📄 License
MIT © ApexIQ

---

<div align="center">
Built for the era of Agentic AI Engineering.
</div>
