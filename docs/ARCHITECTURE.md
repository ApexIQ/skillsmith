# Skillsmith Architecture

## Directory Structure

The Skillsmith project follows a clean, modular architecture designed for maintainability and scalability.

```
skills-agent/
├── src/skillsmith/          # Core library
│   ├── core/               # Core abstractions and utilities
│   │   ├── base_command.py # Base class for all commands
│   │   ├── config.py       # Configuration management
│   │   ├── constants.py    # Project constants
│   │   └── exceptions.py   # Custom exceptions
│   │
│   ├── commands/           # CLI commands (organized by category)
│   │   ├── project/        # Project management commands
│   │   ├── skills/         # Skill management commands
│   │   ├── orchestration/  # Multi-agent orchestration
│   │   ├── analysis/       # Analysis and reporting
│   │   └── development/    # Development workflow commands
│   │
│   ├── services/           # Reusable business logic
│   │   ├── registry.py     # Skill registry service
│   │   ├── trust.py        # Trust verification
│   │   ├── workflow.py     # Workflow engine
│   │   └── context_index.py # Context indexing
│   │
│   ├── models/             # Data models and schemas
│   ├── utils/              # Shared utilities
│   └── templates/          # Project templates
│
├── .agent/                 # Agent configuration and memory
│   ├── skills/            # Local skill library
│   ├── logs/              # Event logs and history
│   └── context/           # Project context
│
├── docs/                   # Documentation
│   ├── agents/            # Agent-specific docs
│   ├── commands/          # Command documentation
│   └── recipes/           # Usage examples
│
├── tests/                  # Test suite
└── tmp/                    # Temporary files
```

## Core Components

### 1. Core Abstractions (`src/skillsmith/core/`)
- **BaseCommand**: Abstract base class for all CLI commands
- **SkillsmithConfig**: Central configuration management
- **Constants**: Project-wide constants and configuration values
- **Exceptions**: Custom exception hierarchy

### 2. Command System (`src/skillsmith/commands/`)
Commands are organized by functional category:
- **Project**: init, align, doctor, profile
- **Skills**: add, search, compose, evolve
- **Orchestration**: swarm, team-exec, autonomous
- **Analysis**: audit, report, metrics, context
- **Development**: test, lint, debug, refactor

### 3. Services Layer (`src/skillsmith/services/`)
Reusable business logic that can be used programmatically:
- Registry management
- Trust verification
- Workflow orchestration
- Context indexing

### 4. Memory System (`.agent/`)
Five-layer memory pattern for persistent context:
1. **Observer**: Raw event logging
2. **Reflector**: Log compaction and lessons
3. **Recovery**: Context retrieval
4. **Watcher**: Change detection
5. **Safeguard**: Memory management

## Design Principles

1. **Separation of Concerns**: Clear boundaries between CLI, business logic, and data
2. **Modularity**: Components can be used independently
3. **Testability**: Each component is independently testable
4. **Extensibility**: New commands and services can be added without affecting existing code
5. **Library-First**: Optimized for programmatic use, not just CLI

## Command Flow

```
User Input → CLI Router → Command Class → Service Layer → Models → Output
                              ↓
                         Base Command
                              ↓
                      Config & Validation
```

## Memory Flow

```
Tool Execution → Event Logger → Raw Logs → Compaction → Lessons
                                    ↓
                              Context Index
                                    ↓
                            Retrieval & Reuse
```

## Key Files

- `cli.py`: Main CLI entry point and router
- `api.py`: Programmatic API for library usage
- `memory.py`: Memory management system
- `mcp_server.py`: Model Context Protocol server

## Extension Points

1. **New Commands**: Add to appropriate category in `commands/`
2. **New Services**: Add to `services/` with clear interfaces
3. **New Skills**: Add to `.agent/skills/`
4. **New Templates**: Add to `templates/`

## Configuration

Project configuration is managed through:
- `.agent/project_profile.yaml`: Project metadata
- `.agent/STATE.md`: Current execution state
- `.agent/lessons.md`: Long-term memory
- Platform-specific files (CLAUDE.md, GEMINI.md, etc.)