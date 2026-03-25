# Comprehensive Command Reference

This is the definitive guide to the **Skillsmith CLI**. Every command is designed as a specialized "wedge" to help developers and AI agents build, verify, and scale their projects with 100% architectural integrity.

---

## 🏗 Project Lifecycle

### `skillsmith init`
The foundation. Initializes the `.agent/` context, installs starter skills, and renders tool-native instruction files (CLAUDE.md, Cursor rules, etc.).
- **Flag `--guided`**: Interactive setup with repo inference.
- **Flag `--template`**: Scaffold from high-performance projects (FastAPI, Next.js, etc.).
- **Flag `--minimal`**: Core scaffolding only.

### `skillsmith align`
The "Drift Prevention" engine. Synchronizes all tool-native files (Claude commands, IDE rules) with your `.agent/project_profile.yaml`.
- **Use Case**: Run this after changing your tech stack or adding new tools.

### `skillsmith sync`
The "Context Refresher". Re-scans your repository to detect language, framework, and deployment changes, then updates your project profile without re-running init.
- **Use Case**: Run this after a major dependency update or refactor.

---

## ✅ Quality & Readiness (The CI Gate)

### `skillsmith ready`
The ultimate pre-release sanity check. It runs a suite of high-speed readiness tests (git health, profile consistency, context index freshness) and fails fast on any blockers.
- **Usage**: Typically run in a `pre-commit` hook or `git push` workflow.

### `skillsmith doctor`
A comprehensive diagnostic tool for your AI-engineering environment. It checks if managed files are missing, drifted, or if your PATH is set up correctly.
- **Score**: Emits a `Readiness Score` out of 100.

### `skillsmith audit`
The operator-facing integrity view. It goes deeper than `doctor`, auditing skill checksums, trust provenance, remote source policy, and security vulnerabilities.
- **Flag `--strict`**: Ideal for CI environments to enforce 100% compliance.

---

## ⚡ Agent Workflows

### `skillsmith compose`
The heart of Agentic Engineering. Generates a multi-stage, goal-specific **Workflow Bundle** in `.agent/workflows/`. 
- **Structure**: Includes Stages (Discover -> Plan -> Build -> Review -> Test -> Ship -> Reflect).
- **Feedback**: Automatically incorporates past evaluation results to avoid recurring mistakes.

### `skillsmith suggest`
The "What's Next" engine. Inspects your current repo state and recommends the 1-3 most high-leverage commands to move the project forward.

### `skillsmith autonomous run`
Starts a bounded autonomous loop that executes benchmark-driven tasks with safety guards and preflight checks.

### `skillsmith evolve`
The "Learning Engine". Transforms repository history or raw source code into reusable Agentic Skills.
- **Subcommand `capture`**: Analyzes Git history to extract structural engineering patterns.
- **Subcommand `fix`**: (v1.1.0) Autonomous self-repair. Analyzes performance regressions and generates logic patches for degraded skills.
- **Subcommand `unlabeled`**: Performs unsupervised structural analysis on raw directories to discover "intelligence-rich" patterns (XSkill).

### `skillsmith metrics`
The "ROI Dashboard". Displays performance metrics for your installed skill library, including success rates, application counts, and degradation trends.
- **Flag `--export`**: Export metrics as JSON for CI/CD analytics.

---

## 🔌 External Integration (MCP)

### `skillsmith serve`
Starts the **Skillsmith MCP Server**. This exposes your local skill library as an on-demand "Agentic Tool" for Claude Desktop, Cursor, and Gemini.
- **Transport `stdio`**: Default for local agents like Claude Code.
- **Transport `http`**: Expose as a network service on a specific port.
- **Flag `--port`**: Set a custom HTTP port (default 47731).

---

## 🌲 Reasoning & Swarms

### `skillsmith tree`
The "Reasoning Engine". Generates a recursive **AND/OR Thinking Tree** to resolve complex goals with multiple fallback strategies.

---

## 🔎 Skill Management

### `skillsmith list` & `skillsmith roles`
Inspect your currently installed skills and active subagent personas locally.

### `skillsmith search`
The "CLI Discovery Hub". This command natively queries the external `ghost-content` skills index (889+ skills) and renders an interactive, formatted terminal Explorer.
- **Flag `--categories`**: View the global taxonomy and count of skills per category seamlessly without downloading all skills.
- **Filtering**: Supports `--category` and `--limit` flags to easily hunt down specific ecosystem tools.

### `skillsmith discover` & `skillsmith recommend`
Search the global catalog or get personalized skill suggestions based on your tech stack.

### `skillsmith add`
Install skills from local paths, GitHub URLs, or the global registry.
- **Security**: Verifies publisher signatures before installation.

---

## 🧠 Brain & Context

### `skillsmith context-index`
Manages the retrieval-augmented context for your agents.
- **Subcommand `build`**: Full index rebuild.
- **Subcommand `query`**: Ranked search across the codebase with score breakdowns.
- **Subcommand `recover`**: Restore a known-good index state.

### `skillsmith snapshot`
Save and restore the entire `.agent/` state. Ideal for "check-pointing" before a risky autonomous run.

---

## 🏢 Enterprise & Team (Advanced)

### `skillsmith registry-service` & `skillsmith trust-service`
Run local or team-scoped HTTP APIs for shared skill management and centralized trust authority. Supports RBAC, OIDC, and asymmetric key signatures.

### `skillsmith safety`
Manage repository-wide safety lockdowns (freeze/guard/careful) to restrict agent mutations during sensitive release windows.

### `skillsmith swarm plan`
The "Decomposition Engine". Breaks down a massive goal into a parallelized, multi-agent task graph (Orchestrator, Researcher, Implementer, Reviewer).

### `skillsmith team-exec`
The "High-Velocity Harness". Executes a mission using the full Team Execution Protocol, simulating structured agentic handoffs and verification loops.

---

## 📊 Analytics & Metrics

### `skillsmith eval`
Executes an evaluation benchmark and produces detailed metrics artifacts (`.agent/evals/results/latest.json`).
- **Use Case**: Essential for regression testing and tuning agent prompts.

### `skillsmith budget`
Track and manage token/cost expenditures per project or session.

---

## 🧬 System & Assets

### `skillsmith assets`
Manages the download and caching of heavyweight runtime assets (models, large datasets) that live outside the standard package.

### `skillsmith profile`
View or set project-level configuration (tech stack, trust policy, preferred tools) from the CLI.

---

*Generated by Skillsmith v1.0.0*
