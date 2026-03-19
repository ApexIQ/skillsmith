# Competitive Research

## What adjacent products do well

### `skills.sh`
- Large open directory and simple install flow.
- Strong distribution story for markdown-based skills.
- Clear user value: discover and install instead of writing instructions manually.

### Skyll
- Multi-source aggregation and ranking.
- Dynamic search API and MCP delivery.
- Strong model for freshness and relevance scoring.

### Continue
- Separates reusable prompts/rules from runtime context providers.
- Good pattern for referencing code, files, and diffs on demand instead of preloading everything.

### Aider
- Strong repository understanding via repo map.
- Good example of concise context extraction before task execution.

### Claude Code + MCP
- MCP is becoming the distribution and integration layer for tools and contextual data.
- Project-scoped configuration and shared tool setup are increasingly important.

### Goose
- Recipes package instructions, tools, parameters, and reusable workflow setups.
- Good model for shareable workflow bundles rather than isolated prompt files.

### OpenHands
- Skills can be triggered automatically from context.
- Strong framing around skills plus orchestration plus runtime tools.

## What `skillsmith` should do differently

`skillsmith` should not just be another skill installer.

It should become the orchestration layer that:
- interviews the user,
- infers the project profile,
- chooses the right rules and skills,
- aligns every instruction file,
- produces reusable workflows,
- and keeps the setup current as the repo changes.

## Product Requirements Derived From Research

1. First-run guidance
The user should not have to know which skills exist before getting value.

2. One project profile
Every generated file should be derived from a shared profile, not separate templates.

3. Federated discovery
Search should combine local templates, remote registries, and MCP sources.

4. Trust and provenance
Remote skills need source, author, version, compatibility, and trust scoring.

5. Workflow bundles
Users need reusable execution plans, not just isolated instructions.

6. Progressive delivery
Only the most relevant context should be injected at runtime.

7. Generic but opinionated
Inputs should be generic; outputs should be concrete and execution-oriented.
