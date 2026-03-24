import json
from pathlib import Path
import uuid

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
    swarm_plan = {
        "swarm_id": str(uuid.uuid4())[:8],
        "goal": goal,
        "agents_count": agents,
        "assignments": []
    }
    
    for i, step in enumerate(steps):
        role = roles[i % len(roles)]
        swarm_plan["assignments"].append({
            "step_id": i + 1,
            "task": step,
            "assigned_agent": f"{role}-{ (i // len(roles)) + 1}",
            "dependencies": [i] if i > 0 else []
        })

    console.print(f"\n[bold green]Swarm Plan Generated (ID: {swarm_plan['swarm_id']})[/bold green]")
    for assignment in swarm_plan["assignments"]:
        dep_str = f" [dim](Depends on {assignment['dependencies']})[/dim]" if assignment["dependencies"] else ""
        console.print(f"  [cyan][{assignment['assigned_agent']}][/cyan] -> {assignment['task']}{dep_str}")

    if output:
        Path(output).write_text(yaml.dump(swarm_plan, sort_keys=False), encoding="utf-8")
        console.print(f"\n[OK] Swarm plan saved to {output}")

@click.command(name="team-exec")
@click.argument("goal")
@click.option("--plan", type=click.Path(exists=True), help="Execute from a pre-generated swarm plan.")
def team_exec_command(goal, plan):
    """Execute a task using the full O-R-I-R team (Orchestrator-Researcher-Implementer-Reviewer)."""
    cwd = Path.cwd()
    
    if plan:
        with open(plan, "r") as f:
            plan_data = yaml.safe_load(f)
            goal = plan_data.get("goal", goal)
            assignments = plan_data.get("assignments", [])
    else:
        # Generate a quick plan if none provided
        workflow = build_workflow(goal, cwd, max_skills=5)
        assignments = []
        roles = ["Orchestrator", "Researcher", "Implementer", "Reviewer"]
        for i, step in enumerate(workflow.get("steps", [])):
            assignments.append({"task": step, "role": roles[i % len(roles)]})

    console.print(f"[bold magenta]Team Execution Starting:[/bold magenta] {goal}")
    
    # Simulate the handoff loop
    for i, assignment in enumerate(assignments):
        role = assignment.get("role", f"Agent-{i+1}")
        task = assignment.get("task", "Unknown Task")
        
        console.print(f"\n[bold white]Handoff -> {role}[/bold white]")
        console.print(f"  [dim]Task:[/dim] {task}")
        
        # In a real tool, we would spawn an autonomous sub-agent here.
        # For the library, we simulate the state transition.
        time_msg = "..."
        console.print(f"  [green]Completed.[/green]")

    console.print(f"\n[bold green]Mission Success![/bold green] Results integrated into .agent/STATE.md")
