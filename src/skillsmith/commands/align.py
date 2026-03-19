from pathlib import Path

import click

from . import console
from .rendering import load_project_profile, render_all


@click.command()
def align_command():
    """Re-render managed files from .agent/project_profile.yaml."""
    cwd = Path.cwd()
    try:
        profile = load_project_profile(cwd)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    render_all(cwd, profile)
    console.print("[green][OK][/green] Re-rendered managed files from .agent/project_profile.yaml")
