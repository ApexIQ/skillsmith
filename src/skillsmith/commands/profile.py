from __future__ import annotations

from pathlib import Path

import click
import yaml

from . import console
from .init import _infer_project_profile, _merge_profile
from .lockfile import (
    _normalize_publisher_key_rotation,
    _normalize_publisher_keys,
    _normalize_publisher_public_keys,
    _publisher_signature_algorithms,
    _publisher_signature_mode,
    _publisher_signature_scheme_mode,
)
from .rendering import load_project_profile, render_all
from .sync import _load_existing_profile


def _profile_path(cwd: Path) -> Path:
    return cwd / ".agent" / "project_profile.yaml"


def _load_or_infer_profile(cwd: Path) -> tuple[dict, bool]:
    profile_path = _profile_path(cwd)
    if profile_path.exists():
        return load_project_profile(cwd), False
    return _infer_project_profile(cwd), True


def _split_csv_values(values: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                items.append(part)
    return list(dict.fromkeys(items))


def _parse_publisher_keys(values: tuple[str, ...]) -> dict[str, str]:
    return _normalize_publisher_keys(_split_csv_values(values))


def _format_publisher_keys(value: dict | list | None) -> list[str]:
    return list(_normalize_publisher_keys(value or {}).keys())


def _parse_publisher_public_keys(values: tuple[str, ...]) -> dict:
    entries = _split_csv_values(values)
    normalized: dict[str, dict[str, object]] = {}
    for entry in entries:
        if "=" not in entry:
            continue
        key_id, key_value = entry.split("=", 1)
        key_id = key_id.strip()
        key_value = key_value.strip()
        if not key_id or not key_value:
            continue
        if ":" in key_value:
            modulus, exponent = key_value.split(":", 1)
        else:
            modulus, exponent = key_value, "65537"
        normalized[key_id] = {"n": modulus.strip(), "e": int(exponent.strip() or "65537", 0)}
    return _normalize_publisher_public_keys(normalized)


def _format_publisher_public_keys(value: dict | list | None) -> list[str]:
    return list(_normalize_publisher_public_keys(value or {}).keys())


def _parse_key_rotation(values: tuple[str, ...]) -> dict:
    if not values:
        return {}
    rotation: dict[str, object] = {}
    for value in _split_csv_values(values):
        for item in value.split(","):
            item = item.strip()
            if not item or "=" not in item:
                continue
            key, raw = item.split("=", 1)
            key = key.strip()
            raw = raw.strip()
            if not key:
                continue
            if key == "previous_key_ids":
                rotation[key] = [part.strip() for part in raw.split("|") if part.strip()]
            elif key == "rotation_grace_period_days":
                try:
                    rotation[key] = max(0, int(raw))
                except Exception:
                    continue
            else:
                rotation[key] = raw
    return _normalize_publisher_key_rotation(rotation)


def _format_key_rotation(value: dict | None) -> str:
    rotation = _normalize_publisher_key_rotation(value or {})
    if not rotation:
        return "none"
    parts = []
    if rotation.get("current_key_id"):
        parts.append(f"current={rotation['current_key_id']}")
    if rotation.get("previous_key_ids"):
        parts.append(f"previous={','.join(rotation['previous_key_ids'])}")
    if rotation.get("rotation_grace_period_days") is not None:
        parts.append(f"grace={rotation['rotation_grace_period_days']}")
    if rotation.get("rotated_at"):
        parts.append(f"rotated_at={rotation['rotated_at']}")
    return " ".join(parts) if parts else "none"


def _write_profile(cwd: Path, profile: dict) -> None:
    profile_path = _profile_path(cwd)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def _apply_profile_updates(
    profile: dict,
    *,
    target_tools: tuple[str, ...],
    priorities: tuple[str, ...],
    trusted_skill_sources: tuple[str, ...],
    allowed_remote_domains: tuple[str, ...],
    min_remote_trust_score: int | None,
    blocked_skill_sources: tuple[str, ...],
    require_pinned_github_refs: bool | None,
    trusted_publisher_keys: tuple[str, ...],
    trusted_publisher_public_keys: tuple[str, ...],
    publisher_signature_scheme_mode: str | None,
    publisher_signature_algorithms: tuple[str, ...],
    publisher_verification_mode: str | None,
    publisher_key_rotation: tuple[str, ...],
    min_remote_freshness_score: int | None,
    required_remote_licenses: tuple[str, ...],
) -> dict:
    updated = dict(profile)
    if target_tools:
        updated["target_tools"] = _split_csv_values(target_tools)
    if priorities:
        updated["priorities"] = _split_csv_values(priorities)
    if trusted_skill_sources:
        updated["trusted_skill_sources"] = _split_csv_values(trusted_skill_sources)
    if allowed_remote_domains:
        updated["allowed_remote_domains"] = _split_csv_values(allowed_remote_domains)
    if min_remote_trust_score is not None:
        updated["min_remote_trust_score"] = max(0, min(100, int(min_remote_trust_score)))
    if blocked_skill_sources:
        updated["blocked_skill_sources"] = _split_csv_values(blocked_skill_sources)
    if require_pinned_github_refs is not None:
        updated["require_pinned_github_refs"] = bool(require_pinned_github_refs)
    if trusted_publisher_keys:
        updated["trusted_publisher_keys"] = _parse_publisher_keys(trusted_publisher_keys)
    if trusted_publisher_public_keys:
        updated["trusted_publisher_public_keys"] = _parse_publisher_public_keys(trusted_publisher_public_keys)
    if publisher_signature_scheme_mode is not None:
        updated["publisher_signature_scheme_mode"] = _publisher_signature_scheme_mode(publisher_signature_scheme_mode)
    if publisher_signature_algorithms:
        updated["publisher_signature_algorithms"] = _publisher_signature_algorithms(publisher_signature_algorithms)
    if publisher_verification_mode is not None:
        updated["publisher_verification_mode"] = _publisher_signature_mode(publisher_verification_mode)
    if publisher_key_rotation:
        updated["publisher_key_rotation"] = _parse_key_rotation(publisher_key_rotation)
    if min_remote_freshness_score is not None:
        updated["min_remote_freshness_score"] = max(0, min(100, int(min_remote_freshness_score)))
    if required_remote_licenses:
        updated["required_remote_licenses"] = _split_csv_values(required_remote_licenses)
    return updated


def _sync_profile_preserving_overrides(cwd: Path, profile: dict) -> dict:
    existing = _load_existing_profile(cwd)
    inferred = _infer_project_profile(cwd)
    synced = _merge_profile(profile or existing, inferred)
    for field in (
        "target_tools",
        "priorities",
        "trusted_skill_sources",
        "allowed_remote_domains",
        "min_remote_trust_score",
        "blocked_skill_sources",
        "require_pinned_github_refs",
        "trusted_publisher_keys",
        "trusted_publisher_public_keys",
        "publisher_signature_scheme_mode",
        "publisher_signature_algorithms",
        "publisher_verification_mode",
        "publisher_key_rotation",
        "min_remote_freshness_score",
        "required_remote_licenses",
    ):
        if field in profile:
            synced[field] = profile[field]
    _write_profile(cwd, synced)
    render_all(cwd, synced)
    return synced


@click.group(help="Inspect and tune the saved project profile.")
def profile_command():
    """Inspect and tune the saved project profile."""


@profile_command.command("show")
def profile_show_command():
    """Show the current project profile."""
    cwd = Path.cwd()
    profile, inferred = _load_or_infer_profile(cwd)
    source = "inferred from repo signals" if inferred else "loaded from .agent/project_profile.yaml"
    console.print(f"[bold]Project Profile[/bold] [dim]({source})[/dim]")
    console.print(yaml.safe_dump(profile, sort_keys=False).rstrip())


@profile_command.command("set")
@click.option("--target-tools", multiple=True, help="Target tools to keep in the profile; may be repeated or comma-separated")
@click.option("--priorities", multiple=True, help="Priority tags to keep in the profile; may be repeated or comma-separated")
@click.option("--trusted-skill-sources", multiple=True, help="Trusted skill sources to keep in the profile; may be repeated or comma-separated")
@click.option("--allowed-remote-domains", multiple=True, help="Allowed remote install domains; may be repeated or comma-separated")
@click.option("--min-remote-trust-score", type=click.IntRange(0, 100), help="Minimum trust score for remote skill sources")
@click.option("--blocked-skill-sources", multiple=True, help="Remote skill sources to block; may be repeated or comma-separated")
@click.option(
    "--require-pinned-github-refs/--allow-unpinned-github-refs",
    default=None,
    help="Require GitHub install URLs to use commit-pinned refs.",
)
@click.option(
    "--trusted-publisher-keys",
    multiple=True,
    help="Trusted publisher HMAC keys as key_id=secret; may be repeated or comma-separated",
)
@click.option(
    "--trusted-publisher-public-keys",
    multiple=True,
    help="Trusted publisher RSA public keys as key_id=modulus_hex[:exponent]; may be repeated or comma-separated",
)
@click.option(
    "--publisher-signature-scheme-mode",
    type=click.Choice(["auto", "hmac", "rsa"], case_sensitive=False),
    help="Which publisher signature scheme to prefer or allow",
)
@click.option(
    "--publisher-signature-algorithms",
    multiple=True,
    help="Allowed publisher signature algorithms; may be repeated or comma-separated",
)
@click.option(
    "--publisher-verification-mode",
    type=click.Choice(["off", "optional", "required"], case_sensitive=False),
    help="How strictly to enforce publisher signatures for GitHub installs",
)
@click.option(
    "--publisher-key-rotation",
    multiple=True,
    help="Publisher key rotation metadata as key=value pairs; may be repeated or comma-separated",
)
@click.option("--min-remote-freshness-score", type=click.IntRange(0, 100), help="Minimum freshness score for remote skill sources")
@click.option("--required-remote-licenses", multiple=True, help="Required licenses for remote skill sources; may be repeated or comma-separated")
@click.option("--align", is_flag=True, help="Re-render managed files after saving the profile")
@click.option("--sync", is_flag=True, help="Re-infer repo signals, preserve tuned fields, and re-render managed files")
def profile_set_command(
    target_tools,
    priorities,
    trusted_skill_sources,
    allowed_remote_domains,
    min_remote_trust_score,
    blocked_skill_sources,
    require_pinned_github_refs,
    trusted_publisher_keys,
    trusted_publisher_public_keys,
    publisher_signature_scheme_mode,
    publisher_signature_algorithms,
    publisher_verification_mode,
    publisher_key_rotation,
    min_remote_freshness_score,
    required_remote_licenses,
    align,
    sync,
):
    """Update selected profile fields while preserving unknown keys."""
    cwd = Path.cwd()
    profile, inferred = _load_or_infer_profile(cwd)
    updated = _apply_profile_updates(
        profile,
        target_tools=target_tools,
        priorities=priorities,
        trusted_skill_sources=trusted_skill_sources,
        allowed_remote_domains=allowed_remote_domains,
        min_remote_trust_score=min_remote_trust_score,
        blocked_skill_sources=blocked_skill_sources,
        require_pinned_github_refs=require_pinned_github_refs,
        trusted_publisher_keys=trusted_publisher_keys,
        trusted_publisher_public_keys=trusted_publisher_public_keys,
        publisher_signature_scheme_mode=publisher_signature_scheme_mode,
        publisher_signature_algorithms=publisher_signature_algorithms,
        publisher_verification_mode=publisher_verification_mode,
        publisher_key_rotation=publisher_key_rotation,
        min_remote_freshness_score=min_remote_freshness_score,
        required_remote_licenses=required_remote_licenses,
    )
    _write_profile(cwd, updated)

    if sync:
        updated = _sync_profile_preserving_overrides(cwd, updated)
    elif align:
        render_all(cwd, updated)

    if inferred:
        console.print("[dim]Profile was inferred before updating because no saved profile existed.[/dim]")

    console.print("[green][OK][/green] Updated .agent/project_profile.yaml")
    console.print(
        f"[dim]target_tools={updated.get('target_tools', [])} priorities={updated.get('priorities', [])} "
        f"trusted_skill_sources={updated.get('trusted_skill_sources', [])} "
        f"allowed_remote_domains={updated.get('allowed_remote_domains', [])} "
        f"min_remote_trust_score={updated.get('min_remote_trust_score', 'n/a')} "
        f"blocked_skill_sources={updated.get('blocked_skill_sources', [])} "
        f"require_pinned_github_refs={updated.get('require_pinned_github_refs', True)} "
        f"trusted_publisher_keys={_format_publisher_keys(updated.get('trusted_publisher_keys', {}))} "
        f"trusted_publisher_public_keys={_format_publisher_public_keys(updated.get('trusted_publisher_public_keys', {}))} "
        f"publisher_signature_scheme_mode={updated.get('publisher_signature_scheme_mode', 'auto')} "
        f"publisher_signature_algorithms={_publisher_signature_algorithms(updated.get('publisher_signature_algorithms', []))} "
        f"publisher_verification_mode={updated.get('publisher_verification_mode', 'optional')} "
        f"publisher_key_rotation={_format_key_rotation(updated.get('publisher_key_rotation', {}))} "
        f"min_remote_freshness_score={updated.get('min_remote_freshness_score', 'n/a')} "
        f"required_remote_licenses={updated.get('required_remote_licenses', [])}[/dim]"
    )
