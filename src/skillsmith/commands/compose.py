from pathlib import Path

import click
import yaml

from . import console
from .context_index import build_context_retrieval_trace, persist_context_retrieval_trace, retrieve_context_candidates
from .workflow_engine import build_workflow, load_rolling_eval_feedback


@click.command()
@click.argument("goal", required=False)
@click.option("--goal", "goal_option", help="Workflow goal (backward-compatible alias for positional GOAL).")
@click.option("--max-skills", default=5, show_default=True, help="Maximum skills to include")
@click.option("--mode", type=click.Choice(["standard", "planner-editor"]), default="standard", show_default=True, help="Workflow execution mode")
@click.option("--reflection-retries", default=0, type=click.IntRange(0, 10), show_default=True, help="How many reflection retries to allow after failed verification")
@click.option(
    "--feedback/--no-feedback",
    default=True,
    show_default=True,
    help="Read recent eval artifacts and adjust workflow defaults when signals look risky.",
)
@click.option(
    "--feedback-window",
    default=None,
    type=click.IntRange(1, 20),
    help="Number of recent eval artifacts to consider when feedback is enabled.",
)
@click.option("--output", type=click.Path(), help="Output file (default: stdout)")
def compose_command(goal, goal_option, max_skills, mode, reflection_retries, feedback, feedback_window, output):
    """Generate a workflow using the saved profile, context, and available skills."""
    if goal and goal_option:
        raise click.UsageError("Provide the goal either as positional GOAL or with --goal, not both.")
    resolved_goal = goal_option or goal
    if not resolved_goal:
        raise click.UsageError("Missing goal. Provide GOAL or use --goal <text>.")

    cwd = Path.cwd()
    feedback_artifact = load_rolling_eval_feedback(cwd, feedback_window=feedback_window) if feedback else None
    workflow = build_workflow(
        resolved_goal,
        cwd,
        max_skills=max_skills,
        execution_mode=mode,
        reflection_max_retries=reflection_retries,
        feedback=feedback_artifact,
    )
    trace_path = None
    try:
        candidates = retrieve_context_candidates(cwd, resolved_goal, limit=max_skills, tier="l1")
        trace = build_context_retrieval_trace(
            cwd,
            source="compose",
            query=resolved_goal,
            goal=resolved_goal,
            tier="l1",
            limit=max_skills,
            candidates=candidates,
            selection={
                "selected_skills": [skill.get("name", "") for skill in workflow.get("skills", []) if isinstance(skill, dict)],
                "workflow_steps": len(workflow.get("steps", [])),
            },
            metadata={"mode": mode, "feedback_enabled": bool(feedback)},
        )
        trace_path = persist_context_retrieval_trace(cwd, trace)
        workflow["context_trace"] = trace_path.relative_to(cwd).as_posix()
    except Exception:
        trace_path = None

    if not workflow["skills"]:
        console.print("[yellow]No relevant skills found for that goal.[/yellow]")
        return

    yaml_out = yaml.dump(workflow, sort_keys=False)
    if output:
        Path(output).write_text(yaml_out, encoding="utf-8")
        console.print(f"[green][OK][/green] Workflow written to {output}")
        if trace_path is not None:
            console.print(f"[dim]Retrieval trace: {trace_path.relative_to(cwd).as_posix()}[/dim]")
    else:
        console.print("\n[bold]--- Generated Workflow ---[/bold]")
        console.print(yaml_out)
