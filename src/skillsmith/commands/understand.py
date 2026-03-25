"""Understand-Anything (UA) Intelligence Bridge - CLI Command."""

import click
import json
import shutil
import subprocess
from pathlib import Path

from . import console
from ..services.graph_bridge import GraphBridge
from .init import _write_project_artifacts
from .sync import _load_existing_profile
from .rendering import render_all

@click.group()
def understand_command():
    """Architectural Intelligence Bridge (Codebase Knowledge / CK Integration)."""
    pass

@understand_command.command(name="sync")
@click.option("--deep", is_flag=True, help="Run a full CK architectural scan before syncing profile")
def understand_sync(deep: bool):
    """Deep-Sync: Ingest CK Knowledge Graph into Skillsmith Project Profile."""
    cwd = Path.cwd()
    bridge = GraphBridge(cwd)
    
    # 1. Trigger CK Multi-Agent Scanner if requested
    if deep or not bridge.has_knowledge_graph():
        console.print("[blue][INFO][/blue] Triggering Codebase Knowledge (CK) Multi-Agent Pipeline...")
        # Check if Claude Code or CK is reachable
        try:
             # We attempt to trigger via 'claude code --command /understand'
             # If that fails, we can fall back to a internal 'Baseline' scan if CK is not available
             process = subprocess.run(
                 ["claude", "code", "--command", "/understand"],
                 capture_output=True, text=True, timeout=300
             )
             
             if process.returncode != 0:
                 console.print(f"[yellow][WARN][/yellow] Codebase Knowledge (CK) scan failed or skipped.")
                 # Fallback: Check if we can detect enough to create a baseline
                 if not bridge.has_knowledge_graph():
                     console.print("[dim][INFO][/dim] Falling back to Skillsmith [bold]Structural Baseline[/bold].")
                     baseline_data = bridge.scan_baseline()
                     if bridge.generate_knowledge_graph(baseline_data):
                         console.print("[green][OK][/green] Baseline Intelligence successfully synchronized.")
                     else:
                         console.print("[red][ERROR][/red] Failed to generate baseline graph.")
             else:
                 console.print("[green][OK][/green] CK Knowledge Graph successfully synchronized.")
                 
        except Exception:
             console.print("[yellow][WARN][/yellow] Unable to execute '/understand' via Claude Code.")
             if not bridge.has_knowledge_graph():
                 console.print("[dim][INFO][/dim] Falling back to Skillsmith [bold]Structural Baseline[/bold].")
                 baseline_data = bridge.scan_baseline()
                 if bridge.generate_knowledge_graph(baseline_data):
                     console.print("[green][OK][/green] Baseline Intelligence successfully synchronized.")
                 else:
                     console.print("[red][ERROR][/red] Failed to generate baseline graph.")
    
    # 2. Ingest Graph and Sync Profile
    if not bridge.has_knowledge_graph():
        console.print(f"[red][ERROR][/red] No CK Knowledge Graph found at {bridge.graph_path.relative_to(cwd)}")
        return
        
    console.print("[blue][INFO][/blue] Ingesting Architectural Intelligence from CK Knowledge Graph...")
    existing = _load_existing_profile(cwd)
    if not existing:
        console.print("[red][ERROR][/red] No Skillsmith profile found. Run `skillsmith init` first.")
        return
        
    # Apply CK Intelligence
    updated = bridge.sync_to_profile(existing)
    
    # Update Artifacts
    agents_dir = cwd / ".agent"
    _write_project_artifacts(cwd, agents_dir, updated)
    render_all(cwd, updated)
    
    console.print(f"[green][OK][/green] Synced Skillsmith profile with [bold]{len(updated.get('_ck_hotspots', []))}[/bold] CK hotspots.")
    if "_ck_hotspots" in updated:
        for hotspot in updated["_ck_hotspots"]:
             console.print(f"  - [bold yellow]HOTSPOT[/bold yellow]: {hotspot['path']} (Deps: {hotspot['dependency_count']}, Complexity: {hotspot['complexity_score']:.2f})")

@understand_command.command(name="dashboard")
def understand_dashboard():
    """Launch the CK Visual Dashboard with Skillsmith Metrics Overlays."""
    console.print("[blue][INFO][/blue] Launching Architectural HUD Dashboard...")
    try:
        # We trigger the CK dashboard command via Claude
        subprocess.run(["claude", "code", "--command", "/understand-dashboard"], check=True)
    except Exception as e:
        console.print(f"[red][ERROR][/red] Failed to launch dashboard: {e}")
        console.print("[dim]Visit: .agent/reports/readiness/dashboard.md for static visual fallback.[/dim]")
