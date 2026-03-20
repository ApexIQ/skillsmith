from __future__ import annotations

import json
from pathlib import Path

import click
from rich.table import Table

from . import console
from .lockfile import _timestamp_to_string

SAFETY_DIR = ".agent/safety"
SAFETY_POLICY_FILE = "policy.json"
SAFETY_POLICY_VERSION = 1


def _policy_path(cwd: Path) -> Path:
    return cwd / SAFETY_DIR / SAFETY_POLICY_FILE


def _default_policy() -> dict:
    now = _timestamp_to_string()
    return {
        "version": SAFETY_POLICY_VERSION,
        "generated_at": now,
        "updated_at": now,
        "careful": False,
        "freeze": {
            "enabled": False,
            "target": "",
            "reason": "",
            "updated_at": now,
        },
    }


def _normalize_policy(payload: dict | None) -> dict:
    base = _default_policy()
    if not isinstance(payload, dict):
        return base

    normalized = dict(base)
    normalized["version"] = SAFETY_POLICY_VERSION
    normalized["generated_at"] = str(payload.get("generated_at") or base["generated_at"])
    normalized["updated_at"] = str(payload.get("updated_at") or base["updated_at"])
    normalized["careful"] = bool(payload.get("careful", False))

    freeze = payload.get("freeze", {})
    if not isinstance(freeze, dict):
        freeze = {}
    normalized["freeze"] = {
        "enabled": bool(freeze.get("enabled", False)),
        "target": str(freeze.get("target", "")),
        "reason": str(freeze.get("reason", "")),
        "updated_at": str(freeze.get("updated_at") or normalized["updated_at"]),
    }
    return normalized


def _load_policy(cwd: Path) -> dict:
    path = _policy_path(cwd)
    if not path.exists():
        return _default_policy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_policy()
    return _normalize_policy(payload)


def _write_policy(cwd: Path, payload: dict) -> Path:
    path = _policy_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_policy(payload)
    normalized["updated_at"] = _timestamp_to_string()
    normalized["freeze"]["updated_at"] = normalized["updated_at"]
    path.write_text(json.dumps(normalized, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _apply_careful(policy: dict, enabled: bool) -> dict:
    policy = _normalize_policy(policy)
    policy["careful"] = enabled
    policy["updated_at"] = _timestamp_to_string()
    return policy


def _apply_freeze(policy: dict, *, enabled: bool, target: str = "", reason: str = "") -> dict:
    policy = _normalize_policy(policy)
    policy["freeze"] = {
        "enabled": enabled,
        "target": target,
        "reason": reason,
        "updated_at": _timestamp_to_string(),
    }
    policy["updated_at"] = policy["freeze"]["updated_at"]
    return policy


def _print_policy(policy: dict) -> None:
    freeze = policy.get("freeze", {})
    table = Table(title="Safety Policy", box=None, show_header=False, pad_edge=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Careful", "enabled" if policy.get("careful") else "disabled")
    table.add_row("Freeze", "enabled" if freeze.get("enabled") else "disabled")
    table.add_row("Freeze target", str(freeze.get("target", "")) or "none")
    table.add_row("Freeze reason", str(freeze.get("reason", "")) or "none")
    table.add_row("Policy file", _policy_path(Path.cwd()).relative_to(Path.cwd()).as_posix())
    console.print(table)


@click.group(name="safety", invoke_without_command=True)
@click.pass_context
def safety_command(ctx):
    """Manage local safety modes for agent execution."""
    if ctx.invoked_subcommand is not None:
        return
    policy = _load_policy(Path.cwd())
    console.print("[bold cyan]Safety[/bold cyan]")
    _print_policy(policy)


@safety_command.command("status")
def safety_status_command():
    """Show the current safety policy."""
    policy = _load_policy(Path.cwd())
    console.print("[bold cyan]Safety Status[/bold cyan]")
    _print_policy(policy)


@safety_command.command("careful")
@click.option("--disable", is_flag=True, help="Disable careful mode instead of enabling it.")
def safety_careful_command(disable: bool):
    """Enable or disable careful mode."""
    cwd = Path.cwd()
    policy = _load_policy(cwd)
    policy = _apply_careful(policy, enabled=not disable)
    path = _write_policy(cwd, policy)
    console.print("[bold cyan]Safety[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Careful mode {'enabled' if policy['careful'] else 'disabled'}[/dim]")


@safety_command.command("freeze")
@click.option("--target", default="all-writes", show_default=True, help="Freeze target or scope.")
@click.option("--reason", default="", show_default=False, help="Optional freeze reason.")
def safety_freeze_command(target: str, reason: str):
    """Enable freeze mode for a specific target."""
    cwd = Path.cwd()
    policy = _load_policy(cwd)
    policy = _apply_freeze(policy, enabled=True, target=target, reason=reason)
    path = _write_policy(cwd, policy)
    console.print("[bold cyan]Safety[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Freeze enabled for {policy['freeze']['target']}[/dim]")


@safety_command.command("guard")
@click.option("--target", default="all-writes", show_default=True, help="Freeze target or scope.")
@click.option("--reason", default="", show_default=False, help="Optional freeze reason.")
def safety_guard_command(target: str, reason: str):
    """Enable careful mode and freeze the selected target."""
    cwd = Path.cwd()
    policy = _load_policy(cwd)
    policy = _apply_careful(policy, enabled=True)
    policy = _apply_freeze(policy, enabled=True, target=target, reason=reason)
    path = _write_policy(cwd, policy)
    console.print("[bold cyan]Safety[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(f"[dim]Guard enabled: careful on, freeze on for {policy['freeze']['target']}[/dim]")


@safety_command.command("unfreeze")
@click.option("--disable-careful", is_flag=True, help="Also disable careful mode.")
def safety_unfreeze_command(disable_careful: bool):
    """Clear freeze restrictions while keeping careful mode by default."""
    cwd = Path.cwd()
    policy = _load_policy(cwd)
    if disable_careful:
        policy = _apply_careful(policy, enabled=False)
    policy = _apply_freeze(policy, enabled=False, target="", reason="")
    path = _write_policy(cwd, policy)
    console.print("[bold cyan]Safety[/bold cyan]")
    console.print(f"[green][OK][/green] Wrote {path.relative_to(cwd).as_posix()}")
    console.print(
        f"[dim]Freeze cleared; careful mode {'enabled' if policy['careful'] else 'disabled'}[/dim]"
    )
