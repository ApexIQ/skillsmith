from pathlib import Path

import click

from . import console
from .rendering import load_project_profile, render_all


@click.command()
@click.argument("directory", required=False, type=click.Path(file_okay=False, dir_okay=True, path_type=Path), default=".")
def align_command(directory):
    """Re-render managed files from .agent/project_profile.yaml."""
    cwd = directory.resolve() if directory else Path.cwd()
    try:
        profile = load_project_profile(cwd)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    render_all(cwd, profile)
    console.print("[green][OK][/green] Re-rendered managed files from .agent/project_profile.yaml")
