from pathlib import Path
import json

import click
import yaml

from . import console
from .context_index import build_context_retrieval_trace, persist_context_retrieval_trace, retrieve_context_candidates
from .lockfile import record_skill_usage
from .workflow_engine import build_workflow, load_rolling_eval_feedback


@click.command()
@click.argument("goal", required=False)
@click.option("--goal", "goal_option", help="Workflow goal (backward-compatible alias for positional GOAL).")
@click.option("--max-skills", default=5, show_default=True, help="Maximum skills to include")
@click.option("--mode", type=click.Choice(["standard", "planner-editor"]), default="standard", show_default=True, help="Workflow execution mode")
@click.option("--planner-editor", is_flag=True, hidden=True, help="DEPRECATED: use --mode planner-editor")
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
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON output")
@click.option("--output", type=click.Path(), help="Output file (default: stdout)")
def compose_command(goal, goal_option, max_skills, mode, planner_editor, reflection_retries, feedback, feedback_window, as_json, output):
    """Generate a workflow using the saved profile, context, and available skills."""
    if goal and goal_option:
        raise click.UsageError("Provide the goal either as positional GOAL or with --goal, not both.")
    resolved_goal = goal_option or goal
    if not resolved_goal:
        raise click.UsageError("Missing goal. Provide GOAL or use --goal <text>.")
    if planner_editor:
        console.print("[yellow][DEPRECATED][/yellow] --planner-editor is deprecated; use --mode planner-editor.")
        if mode == "standard":
            mode = "planner-editor"

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
        cache_hit = bool(candidates and candidates[0].get("cache_hit", False))
        cache_age_seconds = candidates[0].get("cache_age_seconds") if candidates else None
        cache_key = candidates[0].get("cache_key") if candidates else None
        trace = build_context_retrieval_trace(
            cwd,
            source="compose",
            query=resolved_goal,
            goal=resolved_goal,
            tier="l1",
            limit=max_skills,
            candidates=candidates,
            selection={
                "selected_skills": list(workflow.get("skills", [])),
                "workflow_steps": len(workflow.get("steps", [])),
                "cache": {
                    "hit": cache_hit,
                    "age_seconds": cache_age_seconds,
                    "key": cache_key,
                },
            },
            metadata={
                "mode": mode,
                "feedback_enabled": bool(feedback),
                "cache": {
                    "hit": cache_hit,
                    "age_seconds": cache_age_seconds,
                    "key": cache_key,
                },
            },
        )
        trace_path = persist_context_retrieval_trace(cwd, trace)
        workflow["context_trace"] = trace_path.relative_to(cwd).as_posix()
    except Exception:
        trace_path = None

    # F1 Telemetry: Record that these skills were applied to a workflow
    try:
        for skill_name in workflow.get("skills", []):
            record_skill_usage(cwd, skill_name, tokens=0) # tokens=0 as this is planning only
    except Exception:
        pass

    payload = {
        "ok": bool(workflow.get("skills")),
        "goal": resolved_goal,
        "cwd": str(cwd),
        "workflow": workflow,
        "trace_path": trace_path.relative_to(cwd).as_posix() if trace_path is not None else None,
    }

    if as_json:
        json_out = json.dumps(payload, indent=2, sort_keys=True)
        if output:
            Path(output).write_text(json_out, encoding="utf-8")
        else:
            click.echo(json_out)
        if not payload["ok"]:
            raise click.exceptions.Exit(1)
        return

    if not payload["ok"]:
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
