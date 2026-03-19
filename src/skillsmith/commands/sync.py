from pathlib import Path

import click
import yaml

from . import console
from .init import _infer_project_profile, _install_recommended_skills, _merge_profile, _write_project_artifacts
from .rendering import render_all


def _load_existing_profile(cwd: Path) -> dict:
    profile_path = cwd / ".agent" / "project_profile.yaml"
    if not profile_path.exists():
        return {}
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


@click.command()
@click.option("--auto-install", is_flag=True, help="Install or refresh recommended skills after syncing")
def sync_command(auto_install):
    """Re-infer the repo profile, re-render managed files, and refresh recommendations."""
    cwd = Path.cwd()
    existing = _load_existing_profile(cwd)
    inferred = _infer_project_profile(cwd)
    profile = _merge_profile(existing, inferred)

    agents_dir = cwd / ".agent"
    agents_dir.mkdir(parents=True, exist_ok=True)
    _write_project_artifacts(cwd, agents_dir, profile)
    render_all(cwd, profile)

    installed = []
    if auto_install:
        installed = _install_recommended_skills(cwd, profile)

    console.print("[green][OK][/green] Synced .agent/project_profile.yaml from current repo signals")
    console.print("[green][OK][/green] Re-rendered managed files from synced profile")
    if installed:
        console.print("[green][OK][/green] Installed recommended skills:")
        for item in installed:
            console.print(f"  - {item['name']}: {'; '.join(item['reasons'][:2])}")
