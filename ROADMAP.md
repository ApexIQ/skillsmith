# 🗺️ Future Roadmap: skillsmith

To evolve from a simple scaffolding tool into a central hub for agentic expertise, here are the proposed future enhancements:

## 1. Dynamic Skill Registry 🌐
- **Remote `add`**: `skillsmith add github:user/repo/skill` to pull community-made skills directly from GitHub.
- **Central Registry**: A hosted API where developers can browse and search for skills.

## 2. Framework-Specific Scaffolding 🔧
- **Integrations**: `skillsmith init --agno` or `--langchain` to generate boilerplate code for specific agent frameworks.
- **Python-Native Skills**: Exporting skills as Python modules that agents can import directly.

## 3. Skill Versioning & Updates 🔄
- **`skillsmith update`**: Intelligent merging of updates to local skills without overwriting project-specific customizations.
- **Version Locking**: Pinning skills to specific versions in an `agents.toml` file.

## 4. Advanced Tooling 🛠️
- **Skill Linting**: `skillsmith lint` to verify skill formatting and link integrity.
- **TUI (Terminal UI)**: An interactive selector for choosing skills during initialization.

## 5. Agent-Centric Features 🤖
- **Skill Discovery**: Allowing agents to search for and install missing skills autonomously.
- **Prompt Templates**: Bundling specific prompt templates with each skill.
