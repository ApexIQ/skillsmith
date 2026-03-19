from pathlib import Path

import click
import yaml

from . import console
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

    feedback_artifact = load_rolling_eval_feedback(Path.cwd(), feedback_window=feedback_window) if feedback else None
    workflow = build_workflow(
        resolved_goal,
        Path.cwd(),
        max_skills=max_skills,
        execution_mode=mode,
        reflection_max_retries=reflection_retries,
        feedback=feedback_artifact,
    )

    if not workflow["skills"]:
        console.print("[yellow]No relevant skills found for that goal.[/yellow]")
        return

    yaml_out = yaml.dump(workflow, sort_keys=False)
    if output:
        Path(output).write_text(yaml_out, encoding="utf-8")
        console.print(f"[green][OK][/green] Workflow written to {output}")
    else:
        console.print("\n[bold]--- Generated Workflow ---[/bold]")
        console.print(yaml_out)
