import click
from . import __version__
from .commands import (
    console,
    init_command,
    align_command,
    sync_command,
    recommend_command,
    report_command,
    profile_command,
    discover_command,
    list_command,
    add_command,
    lint_command,
    compose_command,
    audit_command,
    evolve_command,
    doctor_command,
    eval_command,
    budget_command,
    update_command,
    rebuild_command,
    serve_command,
    snapshot_command,
    watch_command,
    suggest_command,
    roles_command,
    assets_command,
    autonomous_command,
    context_index_command,
    metrics_command,
    search_command,
    understand_command,
    mcp_group,
    registry_command,
    registry_service_command,
    trust_service_command,
    safety_command,
    tree_command,
    swarm_command,
    team_exec_command,
    advanced_group,
    adbce_command,
)
from .commands.ready import ready_command
from .commands.start import start_command
from .commands import commands_command, cookbook_command

@click.group()
@click.version_option(version=__version__, prog_name="skillsmith")
def main():
    """Agentic Skills Library CLI.
    
    - 'skillsmith commands': List all Management (CLI) and Agentic (/) commands.
    - 'skillsmith cookbook': Navigate 50+ Mission Recipes for your agent.
    """
    import sys
    from pathlib import Path
    from .services.tracing import get_mission_control
    
    # 1. Global Mission Control Activation (Azoria Dashboard Sync)
    # If starting the dash, we defer activation until the server is listening
    if len(sys.argv) > 1 and sys.argv[1] == "dash":
        pass
    else:
        mc = get_mission_control(Path.cwd())
        mc.activate()
    
    # 2. Context Compactor (L5 Safeguard)
    agentic_cmds = {"swarm", "compose", "autonomous", "evolve", "adbce"}
    if any(cmd in sys.argv for cmd in agentic_cmds):
        try:
            from .memory import MemoryManager
            mm = MemoryManager(Path.cwd())
            # Estimate density from raw log size (Proxy for Layer 5)
            log_size_kb = mm.raw_log_path.stat().st_size / 1024
            if log_size_kb > 500: # 500KB is a heavy signal
                from rich.console import Console
                console = Console()
                console.print(f"\n[bold yellow]⚠️  CONTEXT DENSITY WARNING ({log_size_kb:.1f} KB)[/bold yellow]")
                console.print("[dim]Your agentic context is reaching 85% density. Recommending 'skillsmith adbce' to compact logs.[/dim]\n")
        except Exception:
            pass

@main.command("dash")
@click.option("--port", default=6006, help="Port for Arize Phoenix (Local Observation).")
def dash_command(port):
    """Launch the Skillsmith Native Dashboard (Mission Control)."""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    
    # Skillsmith Splash Screen
    console.print(Panel.fit(
        "[bold cyan]Skillsmith Mission Control[/bold cyan]\n"
        "[dim]Initializing Local Observability Dashboard...[/dim]",
        border_style="blue"
    ))
    
    # PERSISTENT STORAGE (Immortal Trace DNA)
    from pathlib import Path
    import os
    storage_dir = Path.cwd() / ".phoenix"
    storage_dir.mkdir(exist_ok=True)
    
    # Force Phoenix DB to the project root via Environment Variable
    os.environ["PHOENIX_WORKING_DIRECTORY"] = str(storage_dir.absolute())
    
    try:
        import phoenix as px
        import webbrowser
        
        # 1. Start Server with Persistent Project Storage (Disk-Based)
        console.print(f"[dim]Project Database:[/dim] {storage_dir.absolute()}")
        session = px.launch_app(port=port, use_temp_dir=False)
        
        # 2. Activate Mission Control NOW that the server is listening
        from .services.tracing import get_mission_control
        mc = get_mission_control(Path.cwd())
        mc.activate()
        
        console.print(f"\n[bold green]Dashboard Active![/bold green] View your missions at [underline]{session.url}[/underline]")
        console.print("[dim]Note: Keep this terminal open; data is PERMANENTLY saved to .phoenix/[/dim]")
        
        # FORCE OPEN BROWSER (Aero UX)
        console.print("[blue]Launching browser now...[/blue]")
        webbrowser.open(session.url)
        
        import time
        while True:
            time.sleep(1)
    except ImportError:
        console.print("[red]Error: Arize Phoenix is not installed.[/red]")
        console.print("Run: [bold]pip install skillsmith[observability][/bold]")
    except Exception as e:
        console.print(f"[red]Failed to launch dashboard: {e}[/red]")

# Wire the modular commands
main.add_command(init_command, name="init")
main.add_command(align_command, name="align")
main.add_command(sync_command, name="sync")
main.add_command(recommend_command, name="recommend")
main.add_command(report_command, name="report")
main.add_command(profile_command, name="profile")
main.add_command(discover_command, name="discover")
main.add_command(list_command, name="list")
main.add_command(add_command, name="add")
main.add_command(lint_command, name="lint")
main.add_command(compose_command, name="compose")
main.add_command(audit_command, name="audit")
main.add_command(evolve_command, name="evolve")
main.add_command(doctor_command, name="doctor")
main.add_command(eval_command, name="eval")
main.add_command(budget_command, name="budget")
main.add_command(update_command, name="update")
main.add_command(rebuild_command, name="rebuild")
main.add_command(serve_command, name="serve")
main.add_command(snapshot_command, name="snapshot")
@click.command("audit")
def audit_command():
    """Audit the latest mission for bottlenecks and errors (Mission Control)."""
    from .services.tracing import MissionAuditor
    from rich.table import Table
    from rich.console import Console
    from pathlib import Path
    
    console = Console()
    cwd = Path.cwd()
    project_name = f"skillsmith:{cwd.name}"
    
    with console.status(f"[bold blue]Auditing Mission for {project_name}...[/bold blue]"):
        auditor = MissionAuditor()
        trace = auditor.get_latest_mission_trace(project_name)
        
    if not trace:
        console.print("[yellow]No recent mission traces found in Mission Control.[/yellow]")
        console.print("[dim]Ensure the dashboard is running at 'skillsmith dash'.[/dim]")
        return
        
    console.print(f"\n[bold green]Latest Mission Traced:[/bold green] {trace['goal']}")
    console.print(f"  [dim]Trace ID:[/dim]  {trace['trace_id']}")
    console.print(f"  [dim]Started:[/dim]   {trace['start_time']}")
    
    status_color = "green" if trace["status"] == "OK" else "red"
    console.print(f"  [dim]Status:[/dim]    [{status_color}]{trace['status']}[/{status_color}]")
    
    # Check for bottlenecks or failures
    bottlenecks = auditor.get_mission_bottlenecks(trace['trace_id'])
    if bottlenecks:
        console.print("\n[bold red]Node Failures Found:[/bold red]")
        table = Table(box=None)
        table.add_column("Node Name", style="bold red")
        table.add_column("Error Message", style="dim")
        
        for bn in bottlenecks:
            # Safely extract error or message
            msg = bn.get("attributes", {}).get("exception.message", "Unknown termination")
            table.add_row(bn.get("name", "Unnamed Span"), msg)
        
        console.print(table)
    else:
        console.print("\n[bold green]Audit Clean:[/bold green] No internal agent failures detected.")

main.add_command(audit_command, name="audit")
main.add_command(watch_command, name="watch")
main.add_command(suggest_command, name="suggest")
main.add_command(roles_command, name="roles")
main.add_command(assets_command, name="assets")
main.add_command(autonomous_command, name="autonomous")
main.add_command(context_index_command, name="context-index")
main.add_command(context_index_command, name="context")
main.add_command(start_command, name="start")
main.add_command(ready_command, name="ready")
main.add_command(registry_command, name="registry")
main.add_command(registry_service_command, name="registry-service")
main.add_command(trust_service_command, name="trust-service")
main.add_command(metrics_command, name="metrics")
main.add_command(safety_command, name="safety")
main.add_command(tree_command, name="tree")
main.add_command(swarm_command, name="swarm")
main.add_command(team_exec_command, name="team-exec")
main.add_command(search_command, name="search")
main.add_command(understand_command, name="understand")
main.add_command(mcp_group, name="mcp")
main.add_command(adbce_command, name="adbce")
main.add_command(advanced_group, name="advanced")
main.add_command(commands_command, name="commands")
main.add_command(cookbook_command, name="cookbook")

if __name__ == "__main__":
    main()
