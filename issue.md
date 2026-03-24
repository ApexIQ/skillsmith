# Issues Resolved - 2026-03-24

## 1. Naming Drift in Managed Commands
- **Problem**: The renderer in `rendering.py` was managing 6 commands, while the init process was copying 28+ commands from templates. This created "drift" reported by `skillsmith doctor`.
- **Solution**: Expanded `managed_file_map` and `managed_paths` in `rendering.py` to track all 33+ core commands and workflows.
- **Outcome**: `skillsmith align` now definitively manages every slash command and ensures they stay in sync with the project profile.

## 2. Generic Slash Command Content
- **Problem**: Redirecting slash commands to workflow bundles was functional but basic.
- **Solution**: Enhanced `render_claude_command_from_workflow` to provide a premium, structured interface with Goals, Deep Links to bundles, and top relevant Skills.
- **Outcome**: Every slash command now acts as a high-fidelity entry point for agents.

## 3. Shallow Workflow Bundles
- **Problem**: Workflow bundles only showed the final execution steps summary.
- **Solution**: Updated `workflow_markdown` to include detailed Stages, Objectives, Acceptance Checks, and Evidence requirements.
- **Outcome**: Agents now have rigorous quality gates for EVERY phase of a workflow (Discover -> Plan -> Build -> Review -> Test -> Ship -> Reflect).

## 4. Missing Command Metadata
- **Problem**: Commands like `debug-issue` were in workflow definitions but missing from the Claude command surface.
- **Solution**: Synchronized `workflow_bundle_definitions` and the Claude renderer.
- **Outcome**: 100% feature parity across all platform surfaces.

## 5. Doctor False Positives
- **Problem**: `skillsmith doctor` reported missing files that weren't being tracked properly by the logic.
- **Solution**: Updated the central source of truth for managed paths.
- **Outcome**: Clean bill of health for scaffolded projects.
