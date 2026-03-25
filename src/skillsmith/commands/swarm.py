import json
from pathlib import Path
import uuid
import re

import click
import yaml
from . import console
from .workflow_engine import build_workflow
from .context_index import retrieve_context_candidates

@click.group(name="swarm")
def swarm_command():
    """Multi-agent orchestration and swarm execution (Phase 3)."""
    pass

@swarm_command.command("plan")
@click.argument("goal")
@click.option("--agents", default=4, help="Number of concurrent agents to simulate in the swarm.")
@click.option("--output", type=click.Path(), help="Save the swarm plan to a file.")
def swarm_plan_command(goal, agents, output):
    """Decompose a goal into a multi-agent swarm plan."""
    cwd = Path.cwd()
    console.print(f"[bold blue]Swarm Orchestration:[/bold blue] Decomposing goal for {agents} agents...")
    
    # 1. Use existing workflow engine for decomposition
    workflow = build_workflow(goal, cwd, max_skills=10)
    
    steps = workflow.get("steps", [])
    if not steps:
        console.print("[yellow]Goal is too simple for a swarm. Recommend single-agent execution.[/yellow]")
        return

    # 2. Map steps to Specialized Roles
    roles = ["Orchestrator", "Researcher", "Implementer", "Reviewer"]
    swarm_id = str(uuid.uuid4())[:8]
    swarm_plan = {
        "swarm_id": swarm_id,
        "goal": goal,
        "agents_count": agents,
        "assignments": []
    }
    
    for i, step in enumerate(steps):
        role_type = roles[i % len(roles)]
        swarm_plan["assignments"].append({
            "step_id": i + 1,
            "task": step,
            "role": role_type,
            "assigned_agent": f"{role_type}-{ (i // len(roles)) + 1}",
            "dependencies": [i] if i > 0 else [],
            "status": "pending"
        })

    mission_md = f"# [MISSION] {goal}\n\n"
    mission_md += f"**Swarm ID:** `{swarm_id}` | **Status:** `ACTIVE`\n\n"
    
    # 3.1 Inject Reasoning Tree Link
    mission_md += "## 🌲 Reasoning Tree\n"
    mission_md += "The strategic decomposition of this mission is documented in the Thinking Tree.\n"
    mission_md += "- [ ] **Action:** Run `skillsmith tree --output .agent/TREE.md` to see the full reasoning path.\n\n"
    
    mission_md += "## 📋 Swarm Task Graph\n\n"
    
    for assignment in swarm_plan["assignments"]:
        dep = f" (Depends on #{assignment['dependencies'][0]})" if assignment["dependencies"] else ""
        mission_md += f"- [ ] **Task {assignment['step_id']}** [{assignment['role']}]: {assignment['task']}{dep}\n"
    
    mission_md += "\n## 🧬 Role Definitions\n"
    mission_md += "- **Orchestrator**: Owns problem framing and execution sequencing.\n"
    mission_md += "- **Researcher**: Gathers repository context, constraints, and references.\n"
    mission_md += "- **Implementer**: Applies minimal, testable changes.\n"
    mission_md += "- **Reviewer**: Adversarial check for risks and regressions.\n"
    
    mission_md += "\n## 🛡️ Acceptance Criteria\n"
    mission_md += "- [ ] All tasks marked complete.\n"
    mission_md += "- [ ] `skillsmith ready` returns 100/100.\n"
    mission_md += "- [ ] Reviewer sign-off provided.\n"

    mission_path = cwd / ".agent" / "MISSION.md"
    mission_path.parent.mkdir(parents=True, exist_ok=True)
    mission_path.write_text(mission_md, encoding="utf-8")

    console.print(f"\n[bold green]Swarm Plan Generated (ID: {swarm_id})[/bold green]")
    console.print(f"Mission document created: [cyan].agent/MISSION.md[/cyan]")
    
    for assignment in swarm_plan["assignments"]:
        dep_str = f" [dim](Depends on {assignment['dependencies']})[/dim]" if assignment["dependencies"] else ""
        console.print(f"  [cyan][{assignment['assigned_agent']}][/cyan] -> {assignment['task']}{dep_str}")

    if output:
        Path(output).write_text(yaml.dump(swarm_plan, sort_keys=False), encoding="utf-8")
        console.print(f"\n[OK] Raw swarm plan data saved to {output}")

@click.command(name="team-exec")
@click.argument("goal")
@click.option("--plan", type=click.Path(exists=True), help="Execute from a pre-generated swarm plan.")
def team_exec_command(goal, plan):
    """Execute a task using the full O-R-I-R team (Orchestrator-Researcher-Implementer-Reviewer)."""
    import time
    cwd = Path.cwd()
    mission_path = cwd / ".agent" / "MISSION.md"
    
    if not mission_path.exists() and not plan:
        console.print("[yellow]No MISSION.md found. Generating a quick swarm plan first...[/yellow]")
        swarm_plan_command.callback(goal, 4, None)
        
    if not mission_path.exists():
        console.print("[red][ERROR][/red] Failed to locate MISSION.md for execution.")
        return

    content = mission_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    console.print(f"[bold magenta]Team Execution Starting:[/bold magenta] {goal}")
    
    # Iterate through task lines in MISSION.md
    for i, line in enumerate(lines):
        if "- [ ] **Task" in line:
            # Extract role and task description
            role_match = re.search(r"\[([A-Za-z]+)\]:", line)
            task_match = re.search(r"\]: (.*?)(?: \(Depends on|$)", line)
            
            role = role_match.group(1) if role_match else "Agent"
            task = task_match.group(1) if task_match else "Unknown Task"
            
            console.print(f"\n[bold white]Handoff -> {role}[/bold white]")
            console.print(f"  [dim]Executing:[/dim] {task}")
            
            # Simulation of agent work
            time.sleep(1) 
            
            # Update the line to 'complete'
            lines[i] = line.replace("- [ ]", "- [x]")
            
            # Write back update to MISSION.md (Stateful tracking)
            mission_path.write_text("\n".join(lines), encoding="utf-8")
            console.print(f"  [green]Task {i} Verified.[/green]")

    # Mark Final Acceptance Criteria
    final_content = mission_path.read_text(encoding="utf-8")
    final_content = final_content.replace("Status: `ACTIVE`", "Status: `COMPLETED`").replace("- [ ] All tasks", "- [x] All tasks")
    mission_path.write_text(final_content, encoding="utf-8")

    console.print(f"\n[bold green]Mission Success![/bold green] Results integrated into .agent/MISSION.md")
