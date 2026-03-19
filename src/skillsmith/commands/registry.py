from __future__ import annotations

import json
from pathlib import Path

import click
from rich.table import Table

from . import console
from .lockfile import _timestamp_to_string

REGISTRY_DIR = ".agent/registry"
REGISTRY_FILE = "skills.json"
REGISTRY_VERSION = 2
REGISTRY_STATES = ("draft", "approved", "deprecated")
REGISTRY_APPROVAL_STATES = ("not_requested", "pending", "approved", "rejected", "withdrawn")


def _registry_path(cwd: Path) -> Path:
    return cwd / REGISTRY_DIR / REGISTRY_FILE


def _split_csv_values(values: tuple[str, ...] | list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                items.append(part)
    return list(dict.fromkeys(items))


def _normalize_state(value: str | None) -> str:
    state = str(value or "draft").strip().lower()
    if state not in REGISTRY_STATES:
        raise click.BadParameter(f"state must be one of: {', '.join(REGISTRY_STATES)}")
    return state


def _normalize_approval_state(value: str | None) -> str:
    approval_state = str(value or "not_requested").strip().lower()
    if approval_state not in REGISTRY_APPROVAL_STATES:
        raise click.BadParameter(f"approval state must be one of: {', '.join(REGISTRY_APPROVAL_STATES)}")
    return approval_state


def _find_entry(skills: list[dict], name: str) -> dict | None:
    target = name.strip().lower()
    for entry in skills:
        if str(entry.get("name", "")).strip().lower() == target:
            return entry
    return None


def _entry_owner_list(entry: dict) -> list[str]:
    ownership = entry.get("ownership")
    if isinstance(ownership, dict):
        owners = ownership.get("owners", [])
        if isinstance(owners, list):
            normalized = _split_csv_values([str(item) for item in owners])
            if normalized:
                return normalized

    owners = entry.get("owners", [])
    if isinstance(owners, list):
        return _split_csv_values([str(item) for item in owners])
    return []


def _entry_primary_owner(entry: dict, owners: list[str]) -> str:
    ownership = entry.get("ownership")
    if isinstance(ownership, dict):
        primary = str(ownership.get("primary_owner", "")).strip()
        if primary:
            return primary
    return owners[0] if owners else ""


def _normalize_entry(entry: dict, *, now: str | None = None) -> dict:
    normalized = entry
    owners = _entry_owner_list(normalized)
    if not owners and isinstance(normalized.get("ownership"), dict):
        ownership_owners = normalized["ownership"].get("owners", [])
        if isinstance(ownership_owners, list):
            owners = _split_csv_values([str(item) for item in ownership_owners])
    if not owners and isinstance(normalized.get("owners"), list):
        owners = _split_csv_values([str(item) for item in normalized["owners"]])

    if not now:
        now = _timestamp_to_string()

    normalized["owners"] = owners
    normalized["ownership"] = {
        "owners": owners,
        "primary_owner": _entry_primary_owner(normalized, owners),
    }
    normalized["approvals"] = [item for item in normalized.get("approvals", []) if isinstance(item, dict)]
    normalized["change_history"] = [item for item in normalized.get("change_history", []) if isinstance(item, dict)]
    normalized["approval_status"] = _normalize_approval_state(normalized.get("approval_status"))
    normalized.setdefault("created_at", now)
    normalized.setdefault("updated_at", now)
    normalized.setdefault("lifecycle_state", "draft")
    normalized.setdefault("source", "manual")
    if normalized["lifecycle_state"] == "approved" and normalized["approval_status"] == "not_requested":
        normalized["approval_status"] = "approved"
    if normalized["lifecycle_state"] == "deprecated" and normalized["approval_status"] == "not_requested":
        normalized["approval_status"] = "withdrawn"
    return normalized


def _normalize_registry_payload(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    normalized = dict(payload)
    normalized.setdefault("version", REGISTRY_VERSION)
    normalized.setdefault("generated_at", _timestamp_to_string())
    skills = normalized.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    normalized["skills"] = [_normalize_entry(entry) for entry in skills if isinstance(entry, dict)]
    return normalized


def _empty_registry_payload() -> dict:
    return {
        "version": REGISTRY_VERSION,
        "generated_at": _timestamp_to_string(),
        "skills": [],
    }


def _load_registry(cwd: Path) -> dict:
    path = _registry_path(cwd)
    if not path.exists():
        return _empty_registry_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_registry_payload()
    return _normalize_registry_payload(payload)


def _write_registry(cwd: Path, payload: dict) -> Path:
    path = _registry_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_registry_payload(payload)
    normalized["version"] = REGISTRY_VERSION
    normalized["generated_at"] = _timestamp_to_string()
    path.write_text(json.dumps(normalized, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _record_history(
    entry: dict,
    *,
    action: str,
    actor: str,
    from_state: str | None,
    to_state: str | None,
    note: str | None = None,
) -> None:
    event = {
        "action": action,
        "actor": actor,
        "at": _timestamp_to_string(),
        "from_state": from_state,
        "to_state": to_state,
        "approval_status": entry.get("approval_status", "not_requested"),
    }
    if note:
        event["note"] = note
    entry.setdefault("change_history", [])
    entry["change_history"].append(event)


def _record_approval(
    entry: dict,
    *,
    actor: str,
    from_state: str,
    to_state: str,
    note: str | None = None,
    decision: str = "approved",
) -> None:
    approval = {
        "decision": decision,
        "actor": actor,
        "at": _timestamp_to_string(),
        "from_state": from_state,
        "to_state": to_state,
    }
    if note:
        approval["note"] = note
    entry.setdefault("approvals", [])
    entry["approvals"].append(approval)


def _apply_state_transition(
    entry: dict,
    *,
    action: str,
    actor: str,
    new_state: str | None = None,
    note: str | None = None,
    approval_status: str | None = None,
    record_approval: bool = False,
) -> dict:
    entry = _normalize_entry(entry)
    from_state = str(entry.get("lifecycle_state", "draft"))
    if new_state is None:
        new_state = from_state

    entry["lifecycle_state"] = new_state
    if approval_status is not None:
        entry["approval_status"] = _normalize_approval_state(approval_status)
    elif action == "request-approval":
        entry["approval_status"] = "pending"
    elif action in {"approve"} or new_state == "approved":
        entry["approval_status"] = "approved"
    elif action == "reject":
        entry["approval_status"] = "rejected"
    elif new_state == "deprecated":
        entry["approval_status"] = "withdrawn"
    elif new_state == "draft" and entry.get("approval_status") == "approved":
        entry["approval_status"] = "not_requested"

    if record_approval:
        _record_approval(entry, actor=actor, from_state=from_state, to_state=new_state, note=note)

    _record_history(entry, action=action, actor=actor, from_state=from_state, to_state=new_state, note=note)
    entry["updated_at"] = _timestamp_to_string()
    return entry


def _upsert_skill(
    payload: dict,
    *,
    name: str,
    state: str,
    description: str | None,
    source: str | None,
    owners: tuple[str, ...],
    tags: tuple[str, ...],
    notes: str | None,
    actor: str = "operator",
) -> dict:
    now = _timestamp_to_string()
    skills = payload.setdefault("skills", [])
    entry = _find_entry(skills, name)
    if entry is None:
        entry = {
            "name": name,
            "created_at": now,
            "approvals": [],
            "change_history": [],
        }
        skills.append(entry)
        previous_state = None
    else:
        entry = dict(entry)
        skills[:] = [item for item in skills if str(item.get("name", "")).strip().lower() != name.strip().lower()]
        skills.append(entry)
        previous_state = str(entry.get("lifecycle_state", "draft"))

    entry = _normalize_entry(entry, now=now)
    if previous_state is None:
        previous_state = None
    target_state = _normalize_state(state)

    entry["name"] = name
    entry["lifecycle_state"] = target_state
    entry["updated_at"] = now
    if description is not None:
        entry["description"] = description
    if source is not None:
        entry["source"] = source
    if owners:
        owner_list = _split_csv_values(owners)
        entry["owners"] = owner_list
        entry["ownership"] = {
            "owners": owner_list,
            "primary_owner": owner_list[0] if owner_list else "",
        }
    if tags:
        entry["tags"] = _split_csv_values(tags)
    if notes is not None:
        entry["notes"] = notes

    if target_state == "approved":
        entry["approval_status"] = "approved"
    elif target_state == "deprecated":
        entry["approval_status"] = "withdrawn"
    elif entry.get("approval_status") == "approved" and target_state != "approved":
        entry["approval_status"] = "not_requested"

    action = "create" if previous_state is None else "update"
    _record_history(entry, action=action, actor=actor, from_state=previous_state, to_state=target_state, note=notes)
    return entry


def _set_state(payload: dict, *, name: str, state: str, actor: str = "operator", note: str | None = None) -> dict:
    now = _timestamp_to_string()
    skills = payload.setdefault("skills", [])
    entry = _find_entry(skills, name)
    if entry is None:
        entry = {
            "name": name,
            "created_at": now,
            "approvals": [],
            "change_history": [],
        }
        skills.append(entry)
    else:
        entry = dict(entry)
        skills[:] = [item for item in skills if str(item.get("name", "")).strip().lower() != name.strip().lower()]
        skills.append(entry)

    target_state = _normalize_state(state)
    entry = _apply_state_transition(entry, action="set-state", actor=actor, new_state=target_state, note=note)
    entry.setdefault("created_at", now)
    return entry


def _request_approval(payload: dict, *, name: str, actor: str = "operator", note: str | None = None) -> dict:
    skills = payload.setdefault("skills", [])
    entry = _find_entry(skills, name)
    if entry is None:
        entry = {
            "name": name,
            "created_at": _timestamp_to_string(),
            "approvals": [],
            "change_history": [],
        }
        skills.append(entry)
    else:
        entry = dict(entry)
        skills[:] = [item for item in skills if str(item.get("name", "")).strip().lower() != name.strip().lower()]
        skills.append(entry)
    return _apply_state_transition(entry, action="request-approval", actor=actor, new_state=entry.get("lifecycle_state", "draft"), note=note, approval_status="pending")


def _approve(payload: dict, *, name: str, actor: str = "operator", note: str | None = None) -> dict:
    skills = payload.setdefault("skills", [])
    entry = _find_entry(skills, name)
    if entry is None:
        entry = {
            "name": name,
            "created_at": _timestamp_to_string(),
            "approvals": [],
            "change_history": [],
        }
        skills.append(entry)
    else:
        entry = dict(entry)
        skills[:] = [item for item in skills if str(item.get("name", "")).strip().lower() != name.strip().lower()]
        skills.append(entry)
    entry = _apply_state_transition(
        entry,
        action="approve",
        actor=actor,
        new_state="approved",
        note=note,
        approval_status="approved",
        record_approval=True,
    )
    return entry


def _reject(payload: dict, *, name: str, actor: str = "operator", note: str | None = None) -> dict:
    skills = payload.setdefault("skills", [])
    entry = _find_entry(skills, name)
    if entry is None:
        entry = {
            "name": name,
            "created_at": _timestamp_to_string(),
            "approvals": [],
            "change_history": [],
        }
        skills.append(entry)
    else:
        entry = dict(entry)
        skills[:] = [item for item in skills if str(item.get("name", "")).strip().lower() != name.strip().lower()]
        skills.append(entry)
    return _apply_state_transition(
        entry,
        action="reject",
        actor=actor,
        new_state=entry.get("lifecycle_state", "draft"),
        note=note,
        approval_status="rejected",
    )


def _filter_skills(
    skills: list[dict],
    *,
    state: str | None,
    source: str | None,
    owner: str | None,
    tag: str | None,
    name: str | None,
    approval_state: str | None,
) -> list[dict]:
    filtered = []
    for raw_entry in skills:
        entry = _normalize_entry(raw_entry)
        entry_state = str(entry.get("lifecycle_state", "draft")).lower()
        if state and entry_state != state:
            continue
        if approval_state and str(entry.get("approval_status", "not_requested")).lower() != approval_state:
            continue
        if source and str(entry.get("source", "")).lower() != source.lower():
            continue
        if owner:
            owners = [str(item).lower() for item in _entry_owner_list(entry)]
            if owner.lower() not in owners:
                continue
        if tag:
            tags = [str(item).lower() for item in entry.get("tags", [])]
            if tag.lower() not in tags:
                continue
        if name and name.lower() not in str(entry.get("name", "")).lower():
            continue
        filtered.append(entry)
    return sorted(filtered, key=lambda item: str(item.get("name", "")).lower())


def _print_registry_table(entries: list[dict], total: int) -> None:
    table = Table(title=f"Registry Skills ({len(entries)}/{total})")
    table.add_column("Name", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Approval", style="yellow")
    table.add_column("Source", style="magenta")
    table.add_column("Owners", style="white")
    table.add_column("Tags", style="dim")
    table.add_column("History", style="blue")
    table.add_column("Updated", style="yellow")
    for entry in entries:
        table.add_row(
            str(entry.get("name", "unknown")),
            str(entry.get("lifecycle_state", "draft")),
            str(entry.get("approval_status", "not_requested")),
            str(entry.get("source", "manual")),
            ", ".join(str(item) for item in _entry_owner_list(entry)) or "none",
            ", ".join(str(item) for item in entry.get("tags", [])) or "none",
            str(len(entry.get("change_history", []))),
            str(entry.get("updated_at", "")),
        )
    console.print(table)
    console.print(f"\n[dim]Showing {len(entries)} matching registry entries.[/dim]")


def _print_history_table(entry: dict) -> None:
    history = entry.get("change_history", [])
    table = Table(title=f"Registry History ({entry.get('name', 'unknown')})")
    table.add_column("At", style="yellow")
    table.add_column("Action", style="cyan")
    table.add_column("From", style="green")
    table.add_column("To", style="green")
    table.add_column("Actor", style="magenta")
    table.add_column("Approval", style="blue")
    table.add_column("Note", style="white")
    for event in history:
        table.add_row(
            str(event.get("at", "")),
            str(event.get("action", "")),
            str(event.get("from_state", "")),
            str(event.get("to_state", "")),
            str(event.get("actor", "")),
            str(event.get("approval_status", "")),
            str(event.get("note", "")),
        )
    console.print(table)
    if not history:
        console.print("[dim]No history recorded for this entry.[/dim]")


@click.group(help="Manage team registry entries and lifecycle states.", invoke_without_command=True)
@click.pass_context
def registry_command(ctx):
    """Manage team registry entries and lifecycle states."""
    if ctx.invoked_subcommand is not None:
        return
    console.print(ctx.get_help())


@registry_command.command("add")
@click.argument("name")
@click.option("--state", default="draft", show_default=True, type=click.Choice(list(REGISTRY_STATES), case_sensitive=False))
@click.option("--description", help="Human-readable entry description")
@click.option("--source", default="manual", show_default=True, help="Registry source or owner system")
@click.option("--owner", "owners", multiple=True, help="Owner name(s); may be repeated or comma-separated")
@click.option("--tag", "tags", multiple=True, help="Entry tag(s); may be repeated or comma-separated")
@click.option("--notes", help="Operator notes")
@click.option("--by", "actor", default="operator", show_default=True, help="Actor recorded in the change history")
def registry_add_command(name, state, description, source, owners, tags, notes, actor):
    """Add or update a registry entry."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _upsert_skill(
        payload,
        name=name,
        state=_normalize_state(state),
        description=description,
        source=source,
        owners=owners,
        tags=tags,
        notes=notes,
        actor=actor,
    )
    path = _write_registry(cwd, payload)
    console.print("[bold cyan]Registry[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(
        f"[dim]Saved {entry['name']} as {entry['lifecycle_state']} "
        f"(approval={entry.get('approval_status', 'not_requested')}, history={len(entry.get('change_history', []))})[/dim]"
    )


@registry_command.command("set-state")
@click.argument("name")
@click.argument("state", type=click.Choice(list(REGISTRY_STATES), case_sensitive=False))
@click.option("--by", "actor", default="operator", show_default=True, help="Actor recorded in the change history")
@click.option("--note", help="Optional transition note")
def registry_set_state_command(name, state, actor, note):
    """Move a registry entry to a new lifecycle state."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _set_state(payload, name=name, state=_normalize_state(state), actor=actor, note=note)
    path = _write_registry(cwd, payload)
    console.print("[bold cyan]Registry[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(
        f"[dim]Moved {entry['name']} to {entry['lifecycle_state']} "
        f"(approval={entry.get('approval_status', 'not_requested')})[/dim]"
    )


@registry_command.command("request-approval")
@click.argument("name")
@click.option("--by", "actor", default="operator", show_default=True, help="Actor recorded in the change history")
@click.option("--note", help="Optional approval request note")
def registry_request_approval_command(name, actor, note):
    """Mark a registry entry as pending approval."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _request_approval(payload, name=name, actor=actor, note=note)
    path = _write_registry(cwd, payload)
    console.print("[bold cyan]Registry[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Requested approval for {entry['name']}[/dim]")


@registry_command.command("approve")
@click.argument("name")
@click.option("--by", "actor", default="operator", show_default=True, help="Actor recorded in the change history")
@click.option("--note", help="Optional approval note")
def registry_approve_command(name, actor, note):
    """Approve a registry entry and record the approval decision."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _approve(payload, name=name, actor=actor, note=note)
    path = _write_registry(cwd, payload)
    console.print("[bold cyan]Registry[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Approved {entry['name']}[/dim]")


@registry_command.command("reject")
@click.argument("name")
@click.option("--by", "actor", default="operator", show_default=True, help="Actor recorded in the change history")
@click.option("--note", help="Optional rejection note")
def registry_reject_command(name, actor, note):
    """Reject a registry approval request."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _reject(payload, name=name, actor=actor, note=note)
    path = _write_registry(cwd, payload)
    console.print("[bold cyan]Registry[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Rejected approval for {entry['name']}[/dim]")


@registry_command.command("history")
@click.argument("name")
def registry_history_command(name):
    """Show the recorded change history for a registry entry."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    entry = _find_entry(payload.get("skills", []), name)
    if entry is None:
        console.print("[bold cyan]Registry History[/bold cyan]")
        console.print(f"[yellow]No registry entry named {name!r} was found.[/yellow]")
        return
    _print_history_table(_normalize_entry(entry))


@registry_command.command("list")
@click.option("--state", type=click.Choice(list(REGISTRY_STATES), case_sensitive=False), help="Filter by lifecycle state")
@click.option("--approval-state", type=click.Choice(list(REGISTRY_APPROVAL_STATES), case_sensitive=False), help="Filter by approval status")
@click.option("--source", help="Filter by source")
@click.option("--owner", help="Filter by owner")
@click.option("--tag", help="Filter by tag")
@click.option("--name", help="Filter by name substring")
def registry_list_command(state, approval_state, source, owner, tag, name):
    """List registry entries with optional filters."""
    cwd = Path.cwd()
    payload = _load_registry(cwd)
    skills = payload.get("skills", [])
    filtered = _filter_skills(
        skills,
        state=_normalize_state(state) if state else None,
        source=source,
        owner=owner,
        tag=tag,
        name=name,
        approval_state=_normalize_approval_state(approval_state) if approval_state else None,
    )
    if filtered:
        _print_registry_table(filtered, len(skills))
    else:
        console.print("[bold cyan]Registry Skills[/bold cyan]")
        console.print(f"[dim]No registry entries matched the current filters ({len(skills)} total entries).[/dim]")
