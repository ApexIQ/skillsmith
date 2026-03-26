import click
from pathlib import Path
from . import console
from .align import align_command
from .doctor import doctor_command
from .budget import budget_command
from .context_index import context_index_command
from .evolve import evolve_command

@click.group(name="advanced")
def advanced_group():
    """Advanced Agentic Operations (ADBCE Flow)."""
    pass

@advanced_group.command(name="flow")
@click.option("--force", is_flag=True, help="Force execution even if errors are found.")
@click.pass_context
def advanced_flow(ctx, force):
    """Execute the standard ADBCE Maintenance Flow.
    
    A: Align instructions
    D: Doctor health check
    B: Budget token analysis
    C: Context indexing
    E: Evolve through reflection
    """
    console.print("[bold cyan]Skillsmith Advanced Flow (ADBCE)[/bold cyan]\n")
    
    # --- A: Align ---
    console.print("[bold blue][STAGE A][/bold blue] Aligning project instructions...")
    ctx.invoke(align_command)
    
    # --- D: Doctor ---
    console.print("\n[bold blue][STAGE D][/bold blue] Running project doctor...")
    ctx.invoke(doctor_command)
    
    # --- B: Budget ---
    console.print("\n[bold blue][STAGE B][/bold blue] Analyzing token budget...")
    ctx.invoke(budget_command)
    
    # --- C: Context ---
    console.print("\n[bold blue][STAGE C][/bold blue] Updating context index...")
    from .context_index import context_index_build_command
    ctx.invoke(context_index_build_command)
    
    # --- E: Evolve ---
    console.print("\n[bold blue][STAGE E][/bold blue] Evolving through reflection...")
    from .evolve import evolve_reflect_command
    ctx.invoke(evolve_reflect_command, force=True)

    console.print("\n[bold green]ADBCE Flow Complete![/bold green] Your agent is now optimally conditioned.")

# Add alias for the user's specific term 'adbce'
@click.command(name="adbce")
@click.pass_context
def adbce_command(ctx):
    """Alias for 'advanced flow'."""
    ctx.forward(advanced_flow)
