# Implementation Plan

## Target Experience

```text
$ skillsmith init --guided

What are you building?
> multi-tenant B2B SaaS for compliance reporting

What stage is the project in?
> greenfield

Which stack should we target?
> Next.js, FastAPI, Postgres

What matters most?
> fast delivery, security, maintainability

Would you like remote skills from trusted registries?
> yes
```

Output:
- `.agent/project_profile.yaml`
- aligned project rule files
- recommended skill set with provenance
- workflow bundles for discovery, implementation, review, and release

## Core Data Model

### `.agent/project_profile.yaml`
- `product_type`
- `project_stage`
- `platforms`
- `frontend`
- `backend`
- `database`
- `deployment`
- `quality_priorities`
- `constraints`
- `team_preferences`
- `allowed_skill_sources`
- `security_policy`

### `skills.lock.json`
- selected skills
- source registry
- version
- checksum
- trust score
- install scope

## New Capabilities

### 1. Guided Init
- Add interview prompts with repo-aware defaults.
- Detect existing stack from lockfiles, manifests, and source tree.
- Save profile first, then render everything else from it.

### 2. Alignment Renderer
- Replace ad hoc template copies with a render pipeline.
- Generate `AGENTS.md`, platform rule files, `.agent/*.md`, and workflow docs from the same profile plus selected skills.
- Separate rendering into artifact classes: rules, skills, workflows, agents, and context.

### 3. Registry Provider Interface
- `LocalTemplateProvider`
- `SkillsShProvider`
- `MCPRegistryProvider`
- `CuratedRegistryProvider`

Each provider should implement:
- `search(query, profile)`
- `get(skill_id)`
- `install(skill, destination)`
- `metadata(skill_id)`

### 4. Skill Ranking
Score by:
- profile fit
- stack compatibility
- task relevance
- popularity
- freshness
- trust/provenance
- local overrides

### 5. Workflow Composer v2
- Move from keyword matching to stage-aware workflow bundles.
- Compose workflows from profile, selected skills, and project maturity.
- Store workflows as reusable markdown/YAML bundles.
- Render tool-native workflow entrypoints separately from internal workflow source docs.

### 6. Drift Detection
- Detect when repo facts no longer match the profile.
- Suggest realignment or new skill recommendations.

### 7. Generated Project Context
- Add a repo analysis step that writes `.agent/context/project-context.md`.
- Refresh this file during setup, alignment, and drift detection flows.
- Use it as input for rules, workflows, and agent routing.

## Delivery Phases

### Milestone A
- `project_profile` schema
- stack inference helpers
- `init --guided`

### Milestone B
- alignment renderer
- generated output parity across platform files

### Milestone C
- provider abstraction
- `skills.sh` search/install integration
- lockfile and provenance tracking

### Milestone D
- workflow composer v2
- recommendation engine
- drift detection

## Success Metrics
- Time from install to useful setup under 2 minutes.
- Users do not need to hand-author the first project rules.
- Generated files stay aligned after profile changes.
- Recommended skills show source and trust metadata.
- Workflows are reusable across repos with the same profile class.
