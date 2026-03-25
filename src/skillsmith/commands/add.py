from pathlib import Path
import shutil
import hashlib
import re
from urllib.parse import urlparse

import click
import yaml

from . import console, download_github_dir, find_template_skill_dir
from .lockfile import record_skill_install
from .lockfile import verify_remote_skill_artifact
from .providers import (
    DiscoveryError,
    SkillCandidate,
    candidate_allowed,
    candidate_install_url,
    discover_skills_with_diagnostics,
    explain_candidate,
)


def _load_profile(cwd: Path) -> dict:
    profile_path = cwd / ".agent" / "project_profile.yaml"
    if not profile_path.exists():
        return {}
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def _annotate_install_candidate(
    candidate: SkillCandidate,
    *,
    install_kind: str,
    selected_by: str,
    requested_name: str | None = None,
    requested_query: str | None = None,
    requested_url: str | None = None,
    selection_mode: str = "manual",
    profile: dict | None = None,
) -> SkillCandidate:
    profile = profile or {}
    metadata = dict(candidate.metadata or {})
    existing_provenance = metadata.get("provenance", {}) if isinstance(metadata.get("provenance"), dict) else {}
    provenance = {
        **existing_provenance,
        "install_kind": install_kind,
        "source": candidate.source,
        "install_ref": candidate.install_ref,
        "requested_name": requested_name,
        "requested_query": requested_query,
        "requested_url": requested_url,
        "selected_by": selected_by,
    }
    query = requested_query or requested_name or candidate.name
    reasons: list[str] = []
    if selection_mode == "manual":
        reasons.append("manual install")
        if install_kind == "manual-url":
            reasons.append("GitHub URL")
        if install_kind == "local-template":
            reasons.append("local template")
    recommendation = {
        "reasons": reasons,
        "selected_by": selected_by,
        "selection_mode": selection_mode,
        "query": query,
    }
    if selection_mode != "manual":
        explanation = explain_candidate(candidate, query, profile)
        recommendation.update(explanation)
    if candidate.source == "local" and "manual install" not in recommendation["reasons"]:
        recommendation["reasons"].insert(0, "manual install")
    metadata["provenance"] = provenance
    metadata["recommendation"] = recommendation
    candidate.metadata = metadata
    return candidate


_GITHUB_TREE_OR_BLOB_PATTERN = re.compile(r"^https?://github\.com/[^/]+/[^/]+/(tree|blob)/([^/]+)/.+$")
_GITHUB_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _requires_pinned_github_refs(profile: dict | None) -> bool:
    profile = profile or {}
    return bool(profile.get("require_pinned_github_refs", True))


def _github_ref_from_url(url: str) -> str | None:
    match = _GITHUB_TREE_OR_BLOB_PATTERN.match(url.strip())
    if not match:
        return None
    return match.group(2)


def _is_github_install_url(url: str) -> bool:
    return _github_ref_from_url(url) is not None


def _is_pinned_github_ref(value: str | None) -> bool:
    if not value:
        return False
    return _GITHUB_SHA_PATTERN.fullmatch(value.strip()) is not None


def _validate_github_ref_pin(url: str, profile: dict | None) -> tuple[bool, str]:
    if not _is_github_install_url(url):
        return True, ""
    if not _requires_pinned_github_refs(profile):
        return True, ""
    ref = _github_ref_from_url(url)
    if _is_pinned_github_ref(ref):
        return True, ""
    return (
        False,
        "GitHub installs require commit-pinned refs when require_pinned_github_refs is true. "
        "Use a URL like https://github.com/<org>/<repo>/tree/<40-char-commit-sha>/<path>",
    )


def _validate_remote_domain(url: str, profile: dict | None) -> tuple[bool, str]:
    profile = profile or {}
    allowed = {
        str(item).strip().lower()
        for item in profile.get("allowed_remote_domains", ["github.com", "skills.sh"])
        if str(item).strip()
    }
    host = urlparse(url).hostname
    if not host:
        return False, f"install URL '{url}' is invalid"
    host = host.lower()
    if host in allowed or any(host.endswith("." + domain) for domain in allowed):
        return True, ""
    return False, f"remote domain '{host}' is not in allowed_remote_domains {sorted(allowed)}"


def _install_local_skill(cwd: Path, skill_name: str, dest_dir: Path, overwrite: bool = False) -> bool:
    src_dir = find_template_skill_dir(skill_name)
    if not src_dir:
        return False

    target = dest_dir / skill_name
    if target.exists():
        if not overwrite:
            console.print(f"[yellow][SKIP][/yellow] Skill '{skill_name}' already exists in .agent/skills/")
            return True
        shutil.rmtree(target)


    shutil.copytree(src_dir, target)
    record_skill_install(
        cwd,
        _annotate_install_candidate(
            SkillCandidate(
                name=skill_name,
                description="Installed from local template library",
                source="local",
                version="0.0.0",
                install_ref=skill_name,
                trust_score=90,
            ),
            install_kind="local-template",
            selected_by="manual",
            requested_name=skill_name,
            selection_mode="manual",
        ),
        target,
    )
    console.print(f"[green][OK][/green] Added skill: {skill_name}")
    return True


def _is_install_url(name_or_url: str) -> bool:
    return name_or_url.startswith("http")


def _install_from_url(
    cwd: Path,
    url: str,
    dest_dir: Path,
    candidate: SkillCandidate | None = None,
    *,
    requested_query: str | None = None,
    profile: dict | None = None,
    selected_by: str = "manual",
    overwrite: bool = False,
) -> bool:
    domain_ok, domain_reason = _validate_remote_domain(url, profile)
    if not domain_ok:
        console.print(f"[yellow][SKIP][/yellow] {domain_reason}")
        return False
    allowed, reason = _validate_github_ref_pin(url, profile)
    if not allowed:
        console.print(f"[yellow][SKIP][/yellow] {reason}")
        return False

    name = url.rstrip("/").split("/")[-1] or "skill"
    target = dest_dir / name
    if target.exists():
        if not overwrite:
            console.print(f"[yellow][SKIP][/yellow] Skill '{name}' already exists in .agent/skills/")
            return True
        shutil.rmtree(target, ignore_errors=True)

    with console.status(f"[bold green]Downloading {name} from GitHub..."):
        try:
            download_github_dir(url, target)
        except Exception as exc:
            console.print(f"[red]Error downloading skill: {exc}[/red]")
            return False

    verification = verify_remote_skill_artifact(target, profile, cwd=cwd)
    if verification["state"] == "valid":
        console.print(f"[green][OK][/green] {verification['message']}")
    elif verification["state"] == "revoked":
        console.print(f"[yellow][SKIP][/yellow] {verification['message']}")
        shutil.rmtree(target, ignore_errors=True)
        return False
    elif verification["mode"] == "required":
        console.print(f"[yellow][SKIP][/yellow] {verification['message']}")
        shutil.rmtree(target, ignore_errors=True)
        return False
    elif verification["state"] != "skipped":
        console.print(f"[yellow][WARN][/yellow] {verification['message']}")

    chosen = candidate or SkillCandidate(
        name=name,
        description="Installed from GitHub URL",
        source="github",
        install_ref=url,
        trust_score=60,
        metadata={"url": url},
    )
    if not chosen.install_ref:
        chosen.install_ref = url
    ref = _github_ref_from_url(url)
    attestation = {
        "source_domain": urlparse(url).hostname,
        "requested_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
        "resolved_ref": ref,
        "resolved_ref_type": "commit-sha" if _is_pinned_github_ref(ref) else "branch-or-tag",
        "pinned_ref": _is_pinned_github_ref(ref),
        "fetched_at": str(chosen.metadata.get("fetched_at", "")) or None,
    }
    meta = dict(chosen.metadata or {})
    prov = dict(meta.get("provenance", {})) if isinstance(meta.get("provenance"), dict) else {}
    prov.update({k: v for k, v in attestation.items() if v not in (None, "")})
    prov["publisher_verification"] = verification
    prov["publisher_verification_method"] = verification.get("method")
    prov["publisher_verification_algorithm"] = verification.get("algorithm")
    prov["publisher_signature_scheme_mode"] = verification.get("signature_scheme_mode")
    prov["publisher_signature_algorithms"] = verification.get("allowed_algorithms")
    prov["publisher_key_rotation"] = verification.get("key_rotation")
    meta["publisher_verification"] = verification
    meta["publisher_verification_method"] = verification.get("method")
    meta["publisher_verification_algorithm"] = verification.get("algorithm")
    meta["publisher_signature_scheme_mode"] = verification.get("signature_scheme_mode")
    meta["publisher_signature_algorithms"] = verification.get("allowed_algorithms")
    meta["publisher_key_rotation"] = verification.get("key_rotation")
    meta["provenance"] = prov
    chosen.metadata = meta
    chosen = _annotate_install_candidate(
        chosen,
        install_kind="remote-url" if candidate is not None else "manual-url",
        selected_by=selected_by,
        requested_name=name,
        requested_query=requested_query,
        requested_url=url,
        selection_mode="discovery" if candidate is not None else "manual",
        profile=profile,
    )
    record_skill_install(cwd, chosen, target)
    console.print(f"[green][OK][/green] Added skill: {chosen.name} ({chosen.source})")
    return True


def discover_skills(query: str, cwd: Path, source: str = "all", limit: int = 10) -> list[SkillCandidate]:
    results, diagnostics = discover_skills_with_diagnostics(query, cwd, source=source, limit=limit)
    setattr(discover_skills, "_last_diagnostics", diagnostics)
    telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
    setattr(discover_skills, "_last_telemetry", telemetry)
    return results


def _install_from_awesome(cwd: Path, skill_id: str, dest_dir: Path, overwrite: bool = False) -> bool:
    import requests
    from . import console
    from .lockfile import record_skill_install
    
    INDEX_URL = "https://raw.githubusercontent.com/ApexIQ/skillsmith/ghost-content/skills_index.json"
    
    with console.status("[cyan]Searching Ghost Registry...[/cyan]"):
        try:
            resp = requests.get(INDEX_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            console.print(f"[red]Failed to connect to Ghost Registry:[/red] {e}")
            return False

    skill_data = next((s for s in data if s.get("id") == skill_id), None)
    if not skill_data:
        console.print(f"[red]Skill '{skill_id}' not found in the awesome index.[/red]")
        return False
        
    path = skill_data.get("path")
    if not path:
        console.print(f"[red]Skill '{skill_id}' has no path listed.[/red]")
        return False
        
    if not path.endswith("SKILL.md"):
        path = f"{path.rstrip('/')}/SKILL.md"

    skill_url = f"https://raw.githubusercontent.com/ApexIQ/skillsmith/ghost-content/{path}"
    
    target_dir = dest_dir / skill_id
    if target_dir.exists():
        if not overwrite:
            console.print(f"[yellow][SKIP][/yellow] Skill '{skill_id}' already exists in .agent/skills/")
            return True
        shutil.rmtree(target_dir, ignore_errors=True)
        
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "SKILL.md"
    
    with console.status(f"[bold green]Fetching {skill_id}...[/bold green]"):
        try:
            skill_resp = requests.get(skill_url, timeout=10)
            skill_resp.raise_for_status()
            target_file.write_bytes(skill_resp.content)
        except Exception as e:
            console.print(f"[red]Failed to download skill content:[/red] {e}")
            return False

    candidate = SkillCandidate(
        name=skill_id,
        description=skill_data.get("description", "Ghost Skill"),
        source="awesome",
        version="0.0.0",
        install_ref=skill_id,
        trust_score=95,
        metadata=skill_data
    )
    
    candidate = _annotate_install_candidate(
        candidate,
        install_kind="ghost-index",
        selected_by="manual",
        requested_name=skill_id,
        selection_mode="manual",
        profile=_load_profile(cwd)
    )
    record_skill_install(cwd, candidate, target_dir)
    console.print(f"[green][OK][/green] Added skill: {skill_id} (Ghost Registry)")
    return True


@click.command()
@click.argument("name_or_url")
@click.option("--discover", "use_discovery", is_flag=True, help="Search providers and install the top match when possible")
@click.option(
    "--source",
    type=click.Choice(["all", "local", "skills.sh", "huggingface", "github-topics", "org-registry"]),
    default="all",
    show_default=True,
    help="Discovery source",
)
@click.option("--remote", help="Remote source (e.g. 'awesome' to fetch from Ghost Registry)")
@click.option("--overwrite", is_flag=True, help="Overwrite existing skill directory")
def add_command(name_or_url, use_discovery, source, remote, overwrite):
    """Add a skill from local library, GitHub URL, or discovered providers."""
    cwd = Path.cwd()
    dest_dir = cwd / ".agent" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)
    profile = _load_profile(cwd)

    if remote == "awesome":
        if _install_from_awesome(cwd, name_or_url, dest_dir, overwrite=overwrite):
            return
        raise click.exceptions.Exit(1)

    if _is_install_url(name_or_url):
        if _install_from_url(cwd, name_or_url, dest_dir, profile=profile, overwrite=overwrite):
            return
        raise click.exceptions.Exit(1)

    if _install_local_skill(cwd, name_or_url, dest_dir, overwrite=overwrite):
        return

    try:
        suggestions = discover_skills(name_or_url, cwd, source=source, limit=3)
        diagnostics = getattr(discover_skills, "_last_diagnostics", [])
        telemetry = getattr(discover_skills, "_last_telemetry", [])
    except DiscoveryError as exc:
        console.print(f"[red][!!][/red] {exc}")
        suggestions = []
        diagnostics = []
        telemetry = []

    for item in diagnostics:
        console.print(f"[yellow][WARN][/yellow] {item}")
    for item in telemetry:
        console.print(
            f"[dim]telemetry provider={item.get('provider')} status={item.get('status')} "
            f"attempts={item.get('attempts')} elapsed_ms={item.get('elapsed_ms')} "
            f"error_type={item.get('error_type') or 'none'}[/dim]"
        )

    console.print(f"[red]Error: Skill '{name_or_url}' not found locally.[/red]")

    if use_discovery and suggestions:
        for candidate in suggestions:
            if candidate.source == "local":
                if _install_local_skill(cwd, candidate.name, dest_dir, overwrite=overwrite):
                    return
                continue

            allowed, reason = candidate_allowed(candidate, profile)
            if not allowed:
                console.print(f"[yellow][SKIP][/yellow] Discovered skill '{candidate.name}' blocked: {reason}")
                continue

            install_url = candidate_install_url(candidate)
            if not install_url:
                console.print(f"[yellow][SKIP][/yellow] {candidate.name} has no installable URL")
                continue

            pin_ok, pin_reason = _validate_github_ref_pin(install_url, profile)
            if not pin_ok:
                console.print(f"[yellow][SKIP][/yellow] {candidate.name}: {pin_reason}")
                continue

            try:
                if _install_from_url(
                    cwd,
                    install_url,
                    dest_dir,
                    candidate=candidate,
                    requested_query=name_or_url,
                    profile=profile,
                    selected_by="skillsmith-discovery",
                    overwrite=overwrite,
                ):
                    return
            except Exception as exc:
                console.print(f"[yellow][SKIP][/yellow] Failed to install {candidate.name}: {exc}")

    if suggestions:
        console.print("[yellow]Try one of these discovered skills:[/yellow]")
        for candidate in suggestions:
            console.print(f"  - {candidate.name} [{candidate.source}] install ref: {candidate.install_ref}")
        console.print("[dim]Use `skillsmith add <query> --discover` to install the top supported match.[/dim]")
    else:
        console.print("[dim]Use `skillsmith discover <query>` to search local and remote providers.[/dim]")
    raise click.exceptions.Exit(1)
