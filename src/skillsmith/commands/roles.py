from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import yaml
from rich.table import Table

from . import console, iter_skill_dirs, load_catalog


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _parse_role_skill_file(skill_md: Path) -> dict[str, Any] | None:
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        return None
    name = str(meta.get("name") or skill_md.parent.name).strip()
    if not name:
        return None
    description = str(meta.get("description") or "").strip()
    return {
        "name": name,
        "description": description,
        "tags": _normalize_tags(meta.get("tags")),
        "version": str(meta.get("version") or ""),
        "path": str(skill_md.parent),
        "source": "project",
    }


def _load_project_roles(cwd: Path) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for skill_dir in iter_skill_dirs(cwd / ".agent" / "skills") or []:
        role = _parse_role_skill_file(skill_dir / "SKILL.md")
        if role:
            roles.append(role)
    return roles


def _load_catalog_roles() -> list[dict[str, Any]]:
    catalog = load_catalog()
    if not catalog:
        return []
    if isinstance(catalog, dict):
        if isinstance(catalog.get("skills"), dict):
            entries = list(catalog.get("skills", {}).values())
        elif isinstance(catalog.get("skills"), list):
            entries = list(catalog.get("skills", []))
        else:
            entries = []
    elif isinstance(catalog, list):
        entries = list(catalog)
    else:
        entries = []

    roles: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        roles.append(
            {
                "name": name,
                "description": str(entry.get("description") or "").strip(),
                "tags": _normalize_tags(entry.get("tags")),
                "version": str(entry.get("version") or ""),
                "path": str(entry.get("path") or ""),
                "source": "catalog",
            }
        )
    return roles


def _filtered_roles(
    roles: list[dict[str, Any]],
    *,
    query: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    query_text = (query or "").strip().lower()
    tag_text = (tag or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for role in roles:
        if tag_text and tag_text not in [t.lower() for t in role.get("tags", [])]:
            continue
        if query_text:
            haystack = " ".join(
                [
                    str(role.get("name", "")),
                    str(role.get("description", "")),
                    " ".join(str(t) for t in role.get("tags", [])),
                ]
            ).lower()
            if query_text not in haystack:
                continue
        filtered.append(role)
    filtered.sort(key=lambda item: (str(item.get("name", "")).lower(), str(item.get("source", "")).lower()))
    return filtered


@click.command(name="roles")
@click.option(
    "--source",
    type=click.Choice(["project", "catalog", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Which role source to show.",
)
@click.option("--tag", help="Filter roles by tag.")
@click.option("--search", help="Filter roles by keyword in name/description/tags.")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
def roles_command(source: str, tag: str | None, search: str | None, json_output: bool) -> None:
    """Browse role-oriented skills from project and catalog sources."""
    cwd = Path.cwd()
    all_roles: list[dict[str, Any]] = []
    if source in ("project", "all"):
        all_roles.extend(_load_project_roles(cwd))
    if source in ("catalog", "all"):
        all_roles.extend(_load_catalog_roles())
    roles = _filtered_roles(all_roles, query=search, tag=tag)

    if json_output:
        payload = {
            "ok": True,
            "cwd": str(cwd),
            "source": source,
            "count": len(roles),
            "roles": roles,
        }
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    if not roles:
        console.print("[yellow]No roles found for the selected filters.[/yellow]")
        if source in ("catalog", "all"):
            console.print("[dim]Hint: run 'skillsmith assets bootstrap' to refresh local catalog assets.[/dim]")
        return

    table = Table(title=f"Role Catalog ({len(roles)})")
    table.add_column("Role", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Tags", style="magenta")
    table.add_column("Description", style="white")
    for role in roles:
        description = str(role.get("description", ""))
        if len(description) > 96:
            description = description[:93] + "..."
        table.add_row(
            str(role.get("name", "")),
            str(role.get("source", "")),
            ", ".join(role.get("tags", [])),
            description,
        )
    console.print(table)
