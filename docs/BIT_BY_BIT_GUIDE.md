# [docs/BIT_BY_BIT_GUIDE.md] / Skillsmith Bit-by-Bit User Journey

This guide explains every command in the Skillsmith ecosystem, why you should use it, and how it level-ups your project intelligence.

---

## 🏗️ Level 1: Induction & Scaffolding (Day 1)
**Goal:** Introduce Skillsmith to your project and stabilize the environment.

### 1. `skillsmith init`
*   **What is it?** The "Front Door" of the Skillsmith ecosystem. It scans your project directory for languages (Python, TS, Go), frameworks (FastAPI, React), and package managers (uv, pnpm).
*   **When to use it?** 
    *   **New project:** `skillsmith init --template <type>` scaffolds a professional architecture immediately.
    *   **Existing project:** `skillsmith init` (no flags) infers a project profile from your existing code.
*   **Success Signal:** A `.agent/project_profile.yaml` file appears in your root.

### 2. `skillsmith align`
*   **What is it?** The "Stability Guard." It ensures all required `.agent/` files, workflows, and skills are present and not corrupted.
*   **When to use it?** If you accidentally delete a rule file or if your "Readiness Score" drops.
*   **Success Signal:** Terminal returns `[OK] Re-rendered managed files`.

---

## 🧠 Level 2: Architectural Intelligence (The CK Bridge)
**Goal:** Give your agent a "Map" of your entire codebase, not just a list of files.

### 3. `skillsmith understand sync --deep`
*   **What is it?** Triggers the **Codebase Knowledge (CK)** bridge. It uses a multi-agent pipeline to scan relationships, class structures, and dependency layers.
*   **When to use it?** After a major refactor or when building a complex system.
*   **Success Signal:** `Synced Skillsmith profile with [X] CK hotspots`.

### 4. `skillsmith understand dashboard`
*   **What is it?** Launches an interactive visual HUD (Heads-Up Display) of your codebase.
*   **When to use it?** When you need to explain code structure or identify which parts are too complex ("hotspots").

---

## 🛠️ Level 3: Professional Acquisition
**Goal:** "Hire" subagents with specialized skills to help you build.

### 5. `skillsmith search <query>`
*   **What is it?** Discovery for the global 889+ skill library (The Ghost Branch).
*   **Example:** `skillsmith search postgres` vs `skillsmith search security`.

### 6. `skillsmith add <id> --remote awesome`
*   **What is it?** The "Hiring Agent." It downloads a signed and verified skill directly into your repo.
*   **When to use it?** When you need specialized expertise for a task (e.g., adding `redis-expert` before doing caching).

---

## 🚀 Level 4: Mission Execution
**Goal:** Put your agent team to work on complex, high-impact goals.

### 7. `skillsmith ready`
*   **What is it?** The "Final Audit." It runs dependency checks, L1/L2 memory verification, and architectural layer validation.
*   **When to use it?** Before every major PR or mission. **Target: 100/100.**

### 8. `skillsmith compose "GOAL"`
*   **What is it?** Synthesizes a specific workflow for a task. It picks the best skills and creates a step-by-step task plan.
*   **When to use it?** For standard, local feature building.

### 9. `skillsmith swarm plan "GOAL"`
*   **What is it?** Orchestrates a "Team" of subagents (Orchestrator, Researcher, Reviewer) for a large-scale migration or refactor.
*   **When to use it?** For "Epic" tasks like "Add full observability to all microservices."

---

## 📈 Level 5: Self-Evolution
**Goal:** Monitor your team and make them smarter.

### 10. `skillsmith metrics`
*   **What is it?** Performance Tracking. It shows success rates, token costs, and throughput for every skill in the repo.
*   **When to use it?** Weekly audits to ensure AI accuracy.

### 11. `skillsmith evolve --mode fix`
*   **What is it?** Self-Healing logic. It analyze failures in your logs and rewrites the `SKILL.md` rules to prevent the same mistake from happening again.
*   **When to use it?** When a skill's success rate is below 80%.

---

## ⚡ Level 6: The AI Command Center (Slash Commands)
**Goal:** Direct your subagent team through 47+ specialized slash commands directly from your IDE.

While the `skillsmith` CLI is for **managing** your environment, these **Slash Commands** are for **executing** missions. Once you have initialized Skillsmith, you can use these shortcuts (prefixed with `/`) to trigger the subagents. See the [Appendix](#appendix-the-complete-command-registry) for the full list of 77+ commands.

### 🍱 The 50+ Command Categorization Map

| Mission Category | Core Slash Commands | When to use? |
| :--- | :--- | :--- |
| **Project Induction** | `/init`, `/sync`, `/align`, `/bootstrap` | When initializing or repairing the Skillsmith link. |
| **Feature Delivery** | `/plan-feature`, `/implement-feature`, `/ready` | To move a feature from idea to executable code. |
| **Quality Control** | `/test`, `/review-changes`, `/lint`, `/audit` | Before merging code to ensure 100% compliance. |
| **Refactoring** | `/refactor`, `/cleanup`, `/migrate`, `/modernize` | To pay down technical debt or upgrade frameworks. |
| **Troubleshooting** | `/debug`, `/fix`, `/verify`, `/performance` | When code breaks or latency spikes. |
| **Intelligence** | `/explain`, `/context`, `/search`, `/report` | To understand complex code or generate documentation. |
| **Auto-Evolution** | `/evolve`, `/metrics`, `/autonomous`, `/benchmark` | For self-scaling and automated skill repairs. |

---

## 🏗️ Real-World Scenario: "Building a New API Endpoint"

Here is how you would use the most important commands in order to deliver a feature pro-style:

1.  **Intellgence Check**: Run `/context` to gather all relevant code files into the subagent's mind-map.
2.  **Planning Phase**: Run `/plan-feature "Add a POST /payments endpoint using Stripe"` to get a technical design.
3.  **Implementation**: Run `/implement-feature` to have the subagent write the controllers, models, and services.
4.  **Verification**: Run `/test` to auto-generate and run the test suite.
5.  **Documentation**: Run `/doc` to update the API README and inline comments.
6.  **Readiness Check**: Run `/ready` to ensure the project meets all 100/100 quality gates.

---

## 🍳 The Skillsmith Mission Cookbook
Find 50+ real-world "Recipes" for building, scaling, and evolving your software with agentic subagents. This is the definitive "How-to" guide for the ecosystem.

### **[👉 Open the Cookbook (docs/COOKBOOK.md)](file:///c:/Users/vanam/Desktop/skills-agent/docs/COOKBOOK.md)**

---

## 📚 Appendix: The Complete Command Registry
Below is the exhaustive list of every command available in the Skillsmith ecosystem.

### 1. Management CLI Commands (`skillsmith <cmd>`)
These commands are used in your terminal to manage the Skillsmith environment and project metadata.

| Command | Description |
| :--- | :--- |
| `add` | Add package dependencies or install new skills. |
| `align` | Force-sync and repair generated .agent files and workflows. |
| `compose` | Synthesize a step-by-step agentic workflow for a specific goal. |
| `config` | View or modify the current Skillsmith configuration. |
| `doctor` | Run diagnostic checks and auto-fix environment inconsistencies. |
| `evolve` | Trigger autonomous skill synthesis or repair cycles. |
| `init` | Initialize the .agent/ structure and infer project DNA. |
| `lint` | Validate the structure and metadata of local skills. |
| `list` | List all available skills from the local and global catalogs. |
| `metrics` | Display skill usage, reliability, and token-cost analytics. |
| `profile` | Inspect or tune the project's behavioral profile. |
| `ready` | Run the high-level readiness gate (Alignment + Sync + Doctor). |
| `rebuild` | Reconstruct the local skill catalog from the skills directory. |
| `recommend` | Preview recommended skills based on project dependencies. |
| `registry` | Manage team-level skill registry and lifecycle states. |
| `report` | Generate a comprehensive summary of project state and trust levels. |
| `roles` | Browse role-oriented skills (Orchestrator, Researcher, etc.). |
| `safety` | Manage safety modes and execution guards for AI loops. |
| `search` | Discover new intelligence from the global "Ghost" library. |
| `serve` | Start the Skillsmith MCP server for IDE agent integration. |
| `snapshot` | Save or restore a stateful snapshot of your .agent/ context. |
| `start` | Run the default "Bootstrap-to-Readiness" path for new users. |
| `suggest` | Predictively suggest the next best command based on context. |
| `swarm` | Orchestrate deterministic multi-agent mission control (Phase 4). |
| `sync` | Re-scan repo signals and update the project profile. |
| `team-exec` | High-level alias for `swarm plan` followed by execution. |
| `tree` | Visualize the current agentic Thinking Tree (AND/OR logic). |
| `understand` | Architectural Intelligence Bridge (CK Knowledge Graph). |
| `update` | Update local skill files to match upstream library templates. |
| `watch` | Monitor for context drift and keep the agent state fresh. |

### 2. Agentic Slash Commands (`/<cmd>`)
These commands are triggered directly inside your IDE (Claude, Cursor, Windsurf) to direct the subagents.

| Command | Role / Purpose |
| :--- | :--- |
| `/init` | Initialize the agent's internal state for a new session. |
| `/sync` | Re-read the Skillsmith profile and project context. |
| `/align` | Ensure the workspace is stable before starting a task. |
| `/bootstrap` | Fast-track a new repo into the Skillsmith ecosystem. |
| `/plan-feature` | Generate a technical design/PRD for a new feature. |
| `/implement-feature` | Write the code and tests for a planned feature. |
| `/ready` | Final quality gate check before merging or shipping. |
| `/test` | Auto-generate, iterate, and run test suites. |
| `/review-changes` | Perform a deep peer-review of current uncommitted changes. |
| `/review` | General architectural or code review of a specific path. |
| `/refactor` | Propose and apply architectural improvements. |
| `/cleanup` | Remove dead code, fix naming, and improve readability. |
| `/migrate` | Help migrating code across versions or frameworks. |
| `/modernize` | Update legacy patterns to modern standards. |
| `/debug` | Investigate and root-cause complex run-time or build errors. |
| `/fix` | Apply targeted fixes for a known bug or linting error. |
| `/lint` | Scan and repair linting violations across the codebase. |
| `/verify` | Execute verification points to confirm a task's success. |
| `/explain` | Explain a complex file, function, or architectural layer. |
| `/context` | Synthesize a context-map of relevant files for the current task. |
| `/search` | Search the codebase or external documentation. |
| `/report` | Generate a status report of the current mission progress. |
| `/metrics` | View performance data for the involved skills. |
| `/autonomous` | Launch a Bounded Execution Loop for long-running tasks. |
| `/evolve` | Request the agent to self-heal its own skill definitions. |
| `/benchmark` | Run comparative performance tests on a feature. |
| `/security` | Perform a security audit focusing on OWASP patterns. |
| `/performance` | Analyze and optimize for latency and resource usage. |
| `/doc` | Update project documentation and API reference. |
| `/profile` | Inspect the persona settings of the current subagent. |

---

## 💡 Pro-Tip: The "Golden Workflow"
1. `init` ⮕ `understand` ⮕ `add` ⮕ `ready` ⮕ `/plan-feature` ⮕ `/implement-feature` ⮕ `/test` ⮕ `metrics` ⮕ `evolve`.
