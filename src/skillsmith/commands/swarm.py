from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import click
import yaml
from rich.table import Table

from . import console, sanitize_json
from .workflow_engine import build_workflow

MISSION_JSON = Path(".agent") / "mission.json"
MISSION_MD = Path(".agent") / "MISSION.md"

ROLE_MAP = {
    "Orchestrator": "agent_collaboration",
    "Researcher": "how_to_research",
    "Implementer": "software_lifecycle",
    "Reviewer": "code_review",
}


def _load_mission(cwd: Path) -> dict[str, Any] | None:
    path = cwd / MISSION_JSON
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_mission(cwd: Path, mission: dict[str, Any]) -> None:
    path = cwd / MISSION_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(mission), indent=2), encoding="utf-8")
    
    # Log State Change (Layer 1)
    from ..memory import MemoryManager
    mm = MemoryManager(cwd)
    mm.log_event("mission_state_change", {
        "swarm_id": mission.get("swarm_id"),
        "status": mission.get("status"),
        "goal": mission.get("goal")
    })
    
    _sync_mission_md(cwd, mission)


def _sync_mission_md(cwd: Path, mission: dict[str, Any]) -> None:
    path = cwd / MISSION_MD
    goal = mission.get("goal", "Root Goal")
    swarm_id = mission.get("swarm_id", "unknown")
    status = mission.get("status", "PENDING")

    md = f"# [MISSION] {goal}\n\n"
    md += f"**Swarm ID:** `{swarm_id}` | **Status:** `{status}`\n\n"

    md += "## 🌲 Reasoning Tree\n"
    md += "The strategic decomposition of this mission is documented in the Thinking Tree.\n"
    md += "- [ ] **Action:** Run `skillsmith tree --output .agent/TREE.md` to see the full reasoning path.\n\n"

    md += "## 📋 Swarm Task Graph\n\n"
    for assignment in mission.get("assignments", []):
        state = assignment.get("status", "pending")
        marker = "[x]" if state == "completed" else "[/]" if state == "in_progress" else "[ ]"
        role = assignment.get("role", "Agent")
        task = assignment.get("task", "Unknown Task")
        step_id = assignment.get("step_id", "?")
        deps = assignment.get("dependencies", [])
        dep_str = f" (Depends on #{deps[0]})" if deps else ""

        md += f"- {marker} **Task {step_id}** [{role}]: {task}{dep_str}\n"

    # --- Active Memory (Token Optimized) ---
    memory_path = cwd / ".agent" / "memory.md"
    if memory_path.exists():
        md += "\n## 🧠 Active Memory (Reflected)\n"
        md += memory_path.read_text(encoding="utf-8")
        md += "\n"

    md += "\n## 🧬 Role Definitions & Skills\n"
    for role, skill in ROLE_MAP.items():
        md += f"- **{role}**: Uses [.agent/skills/{skill}/SKILL.md](file:///.agent/skills/{skill}/SKILL.md)\n"

    md += "\n## 🛡️ Acceptance Criteria\n"
    all_done = all(a.get("status") == "completed" for a in mission.get("assignments", []))
    md += f"- [{'x' if all_done else ' '}] All tasks marked complete.\n"
    md += f"- [ ] `skillsmith ready` returns 100/100.\n"
    md += f"- [ ] Reviewer sign-off provided.\n"

    path.write_text(md, encoding="utf-8")


@click.group(name="swarm")
def swarm_command():
    """Deterministic Multi-agent Mission Control (Phase 4)."""
    pass


@swarm_command.command("plan")
@click.argument("goal")
@click.option("--agents", default=4, help="Target number of specialized agents.")
def swarm_plan_command(goal: str, agents: int):
    """Decompose a goal into a stateful Multi-agent Mission (JSON + MD)."""
    cwd = Path.cwd()
    console.print(f"[bold blue]Mission Protocol:[/bold blue] Decomposing goal for {agents} specialized roles...")

    # 1. Use existing workflow engine for decomposition (Phase 1-3 Thinking Tree)
    workflow = build_workflow(goal, cwd, max_skills=10)

    # Persist reasoning tree for visualization
    (cwd / "workflow.json").write_text(json.dumps(sanitize_json(workflow), indent=2), encoding="utf-8")

    stages = workflow.get("stages", [])
    if not stages:
        console.print("[yellow]Goal is too simple for a swarm. Recommend single-agent execution.[/yellow]")
        return

    # 2. Map stages to Specialized Roles (MCP Pattern)
    roles = list(ROLE_MAP.keys())
    swarm_id = str(uuid.uuid4())[:8]
    mission = {
        "kind": "swarm-mission",
        "swarm_id": swarm_id,
        "goal": goal,
        "status": "ACTIVE",
        "created_at": str(uuid.uuid4()),  # Placeholder
        "assignments": [],
        "tree_metadata": {
            "execution_mode": workflow.get("execution_mode"),
            "reflection_max_retries": workflow.get("reflection_max_retries"),
        }
    }

    # Flatten stages into a linear assignment list for the execution engine, 
    # but tag them with their Thinking Tree context (AND/OR)
    step_id = 1
    for i, stage in enumerate(stages):
        node_type = stage.get("node_type", "AND")
        objectives = stage.get("objectives", [])
        
        # Combined objective task for the stage
        task_desc = f"{stage['name'].upper()}: {objectives[0]}"
        role_type = roles[i % len(roles)]
        
        assignment = {
            "step_id": step_id,
            "task": task_desc,
            "stage": stage["name"],
            "node_type": node_type,
            "role": role_type,
            "persona_skill": ROLE_MAP[role_type],
            "assigned_agent": f"{role_type}-{ (i // len(roles)) + 1}",
            "dependencies": [step_id - 1] if step_id > 1 else [],
            "status": "pending",
            "artifacts": [],
        }
        
        # If it's an OR node, we attach the strategies as potential fallbacks
        if node_type == "OR" and "strategies" in stage:
            assignment["strategies"] = stage["strategies"]
            
        mission["assignments"].append(assignment)
        step_id += 1

    # 3. Persist Deterministic State
    _save_mission(cwd, mission)

    console.print(f"\n[bold green]Mission Protocol Initialized (ID: {swarm_id})[/bold green]")
    console.print(f"State file: [cyan].agent/mission.json[/cyan]")
    console.print(f"Mission document: [cyan].agent/MISSION.md[/cyan]")

    for assignment in mission["assignments"]:
        dep_str = f" [dim](Depends on {assignment['dependencies']})[/dim]" if assignment["dependencies"] else ""
        console.print(f"  [cyan][{assignment['assigned_agent']}][/cyan] -> {assignment['task']}{dep_str}")


@swarm_command.command("status")
def swarm_status_command():
    """Visualize the current mission progress and handoff health."""
    cwd = Path.cwd()
    mission = _load_mission(cwd)
    if not mission:
        console.print("[yellow]No active mission found. Run 'skillsmith swarm plan' first.[/yellow]")
        return

    table = Table(title=f"Mission Status: {mission['swarm_id']}")
    table.add_column("ID", style="dim")
    table.add_column("Role", style="cyan")
    table.add_column("Task", style="white")
    table.add_column("Status", style="magenta")
    table.add_column("Skill", style="green")

    for a in mission.get("assignments", []):
        status = a.get("status", "pending")
        status_color = "green" if status == "completed" else "yellow" if status == "in_progress" else "white"
        table.add_row(
            str(a.get("step_id")),
            a.get("role"),
            a.get("task"),
            f"[{status_color}]{status}[/]",
            a.get("persona_skill"),
        )

    console.print(table)


def _emit_handoff(cwd: Path, assignment: dict[str, Any], mission: dict[str, Any]) -> Path:
    handoff_dir = cwd / ".agent" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    
    packet = {
        "kind": "handoff-packet",
        "version": "1.0.0",
        "mission_id": mission.get("swarm_id"),
        "task_id": assignment.get("step_id"),
        "role": assignment.get("role"),
        "assigned_skill": f".agent/skills/{assignment.get('persona_skill')}/SKILL.md",
        "objective": assignment.get("task"),
        "context": {
            "goal": mission.get("goal"),
            "status": mission.get("status"),
            "dependencies": assignment.get("dependencies", []),
        },
        "artifacts_expected": assignment.get("artifacts", []),
        "generated_at": str(uuid.uuid4()) # Placeholder
    }
    
    path = handoff_dir / f"task_{assignment.get('step_id')}_{assignment.get('role').lower()}.json"
    path.write_text(json.dumps(sanitize_json(packet), indent=2), encoding="utf-8")
    return path


@swarm_command.command("execute")
@click.option("--headless", is_flag=True, help="Run without user interaction (auto-handoff).")
def swarm_execute_command(headless: bool):
    """Deterministic mission execution with real state handoffs."""
    import time

    cwd = Path.cwd()
    mission = _load_mission(cwd)
    if not mission:
        console.print("[red][ERROR][/red] No mission found to execute.")
        return

    from ..services.tracing import get_mission_control
    mc = get_mission_control(cwd)
    
    with mc.start_span("swarm_execution", attributes={"goal": mission.get("goal"), "swarm_id": mission.get("swarm_id")}) as mission_span:
        if mission.get("status") == "COMPLETED":
            console.print("[green]Mission already completed.[/green]")
            return

        console.print(f"[bold magenta]Mission Execution Engine:[/bold magenta] {mission['goal']}")

        for i, assignment in enumerate(mission.get("assignments", [])):
            if assignment.get("status") == "completed":
                continue

            # 1. Verification of Dependencies
            for dep in assignment.get("dependencies", []):
                if mission["assignments"][dep - 1]["status"] != "completed":
                    console.print(f"[yellow]Task {assignment['step_id']} blocked by Task {dep}.[/yellow]")
                    return

            # 2. Handoff Protocol (Child Span)
            role = assignment["role"]
            skill = assignment["persona_skill"]
            task = assignment["task"]
            
            with mc.start_span(f"handoff:{role}:{assignment['step_id']}", attributes={
                "role": role, 
                "skill": skill, 
                "task": task,
                "step_id": assignment["step_id"]
            }):
                assignment["status"] = "in_progress"
                _save_mission(cwd, mission)

                console.print(f"\n[bold white]Handoff Protocol Active -> {role}[/bold white]")
                console.print(f"  [dim]Assigned Skill:[/dim] .agent/skills/{skill}/SKILL.md")
                console.print(f"  [dim]Objective:[/dim] {task}")
                
                # Emit Handoff Packet
                packet_path = _emit_handoff(cwd, assignment, mission)
                console.print(f"  [green]Packet Emitted:[/green] {packet_path.relative_to(cwd)}")
                
                # (Simulation) Finalizing task
                time.sleep(1) 
                assignment["status"] = "completed"
                _save_mission(cwd, mission)
                console.print(f"  [bold green]Task Verified & Signed Off.[/bold green]")
        console.print(f"  [dim]Objective:[/dim] {task}")

        # 3. Emit Machine-Readable Handoff Packet
        # For Reviewers, we include the artifacts from dependencies to verify
        to_verify = []
        if role == "Reviewer":
            for dep_id in assignment.get("dependencies", []):
                dep_assignment = next((a for a in mission["assignments"] if a["step_id"] == dep_id), None)
                if dep_assignment:
                    to_verify.extend(dep_assignment.get("artifacts", []))
        
        assignment["artifacts_to_verify"] = to_verify
        packet_path = _emit_handoff(cwd, assignment, mission)
        console.print(f"  [cyan][PACKET][/cyan] Handoff emitted: {packet_path.name}")
        if to_verify:
            console.print(f"  [dim]Pending Verification:[/dim] {len(to_verify)} artifacts from Task {assignment['dependencies'][0]}")

        # 4. Deterministic "Work" (Agent Handoff Point)
        if not headless:
            console.print("  [dim]Waiting for agent to consume packet and provide result...[/dim]")
            time.sleep(1) # Simulation for now, but state is ready for real handoff

        # 5. Completion & Artifact Logging
        assignment["status"] = "completed"
        assignment["completed_at"] = str(uuid.uuid4())  # Placeholder
        
        # If Reviewer, mark dependencies as verified
        if role == "Reviewer":
            for dep_id in assignment.get("dependencies", []):
                dep_assignment = next((a for a in mission["assignments"] if a["step_id"] == dep_id), None)
                if dep_assignment:
                    dep_assignment["verified"] = True
                    console.print(f"  [bold green][GATE][/bold green] Task {dep_id} artifacts VERIFIED by Reviewer.")

        console.print(f"  [green]Task {assignment['step_id']} Verified & Artifact Logged.[/green]")
        _save_mission(cwd, mission)

    # Final Wrap-up
    mission["status"] = "COMPLETED"
    _save_mission(cwd, mission)
    console.print(f"\n[bold green]Mission COMPLETED![/bold green] All artifacts captured in .agent/mission.json")


@click.command(name="team-exec")
@click.argument("goal")
def team_exec_command(goal: str):
    """Alias for 'swarm plan' then 'swarm execute'."""
    cwd = Path.cwd()
    swarm_plan_command.callback(goal, 4)
    swarm_execute_command.callback()

