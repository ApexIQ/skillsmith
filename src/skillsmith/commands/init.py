import shutil
import zipfile
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import click
import yaml

from rich.console import Console
from rich.prompt import Prompt, Confirm
from . import (
    CORE_SKILLS,
    PLATFORM_DIR,
    PLATFORM_FILES,
    TEMPLATE_DIR,
    console,
    download_github_dir,
    find_template_skill_dir,
    load_catalog,
)
from .assets_runtime import resolve_runtime_asset
from .lockfile import (
    _normalize_publisher_key_rotation,
    _normalize_publisher_keys,
    _normalize_publisher_public_keys,
    _publisher_signature_algorithms,
    _publisher_signature_mode,
    _publisher_signature_scheme_mode,
    record_skill_install,
)
from .providers import SkillCandidate, candidate_install_url, explain_recommendations_for_profile, recommend_skills_for_profile
from .rendering import render_all


def _detect_package_manager(cwd: Path) -> str:
    if (cwd / "uv.lock").exists():
        return "uv"
    if (cwd / "poetry.lock").exists():
        return "poetry"
    if (cwd / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (cwd / "yarn.lock").exists():
        return "yarn"
    if (cwd / "package-lock.json").exists():
        return "npm"
    if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists():
        return "pip"
    return "unknown"


def _split_csv_values(values: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                items.append(part)
    return list(dict.fromkeys(items))


def _detect_languages(cwd: Path) -> list[str]:
    languages = []
    if (cwd / "pyproject.toml").exists() or (cwd / "requirements.txt").exists():
        languages.append("python")
    if (cwd / "package.json").exists():
        languages.append("javascript")
    if any(cwd.rglob("*.ts")) or any(cwd.rglob("*.tsx")):
        languages.append("typescript")
    if any(cwd.rglob("*.go")):
        languages.append("go")
    if any(cwd.rglob("*.rs")):
        languages.append("rust")
    return languages or ["unknown"]


def _detect_frameworks(cwd: Path) -> list[str]:
    frameworks = []
    pyproject = (cwd / "pyproject.toml").read_text(encoding="utf-8", errors="ignore") if (cwd / "pyproject.toml").exists() else ""
    package_json = (cwd / "package.json").read_text(encoding="utf-8", errors="ignore") if (cwd / "package.json").exists() else ""

    for name in ["fastapi", "django", "flask", "click", "pytest", "typer", "streamlit"]:
        if name in pyproject.lower():
            frameworks.append(name)

    for name in ["next", "react", "vite", "vue", "svelte", "express", "nest", "astro", "nuxt"]:
        if f'"{name}"' in package_json.lower():
            frameworks.append(name)

    return sorted(set(frameworks))


def _load_package_json(cwd: Path) -> dict:
    package_json_path = cwd / "package.json"
    if not package_json_path.exists():
        return {}
    try:
        return json.loads(package_json_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detect_app_type(cwd: Path, frameworks: list[str], languages: list[str]) -> str:
    package_json = _load_package_json(cwd)
    package_name = str(package_json.get("name", "")).lower()
    if (cwd / "pyproject.toml").exists() and not (cwd / "package.json").exists():
        return "library"
    if "next" in frameworks or "react" in frameworks or "vue" in frameworks or "svelte" in frameworks:
        if "fastapi" in frameworks or "django" in frameworks or "flask" in frameworks or "express" in frameworks or "nest" in frameworks:
            return "fullstack-app"
        return "web-app"
    if "fastapi" in frameworks or "django" in frameworks or "flask" in frameworks or "express" in frameworks or "nest" in frameworks:
        return "api-service"
    if "cli" in package_name or "click" in frameworks or "typer" in frameworks:
        return "cli-tool"
    if "python" in languages and (cwd / "src").exists():
        return "library"
    return "application"


def _detect_project_stage(cwd: Path) -> str:
    signal_paths = ["src", "tests", "app", "package.json", "pyproject.toml"]
    if any((cwd / item).exists() for item in signal_paths):
        return "existing"
    return "greenfield"


def _detect_commands(cwd: Path, package_manager: str) -> tuple[list[str], list[str]]:
    build_commands = []
    test_commands = []
    package_json = _load_package_json(cwd)
    scripts = package_json.get("scripts", {}) if isinstance(package_json, dict) else {}

    if (cwd / "pyproject.toml").exists():
        if package_manager == "uv":
            build_commands.append("uv build")
        else:
            build_commands.append("python -m build")
        if (cwd / "pytest.ini").exists() or (cwd / "tests").exists():
            test_commands.append("python -m unittest")
        if "pytest" in ((cwd / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")).lower():
            test_commands.insert(0, "pytest")

    if (cwd / "package.json").exists():
        runner = "npm"
        if package_manager == "pnpm":
            runner = "pnpm"
        elif package_manager == "yarn":
            runner = "yarn"
        if "build" in scripts:
            build_commands.append(f"{runner} {'build' if runner == 'yarn' else 'run build'}")
        if "test" in scripts:
            test_commands.append(f"{runner} {'test' if runner == 'yarn' else 'run test'}")
        if not build_commands:
            build_commands.append(f"{runner} {'build' if runner == 'yarn' else 'run build'}")
        if not test_commands:
            test_commands.append(f"{runner} {'test' if runner == 'yarn' else 'run test'}")

    return list(dict.fromkeys(build_commands or ["not-detected"])), list(dict.fromkeys(test_commands or ["not-detected"]))


def _detect_deployment_target(cwd: Path, frameworks: list[str]) -> str:
    if (cwd / "vercel.json").exists() or "next" in frameworks:
        return "vercel"
    if (cwd / "fly.toml").exists():
        return "fly.io"
    if (cwd / "Dockerfile").exists() or (cwd / "docker-compose.yml").exists():
        return "docker"
    if (cwd / "firebase.json").exists():
        return "firebase"
    workflows_dir = cwd / ".github" / "workflows"
    if workflows_dir.exists() and (any(workflows_dir.glob("*.yml")) or any(workflows_dir.glob("*.yaml"))):
        return "github-actions"
    return "not-specified"


def _detect_target_tools(cwd: Path) -> list[str]:
    tools = {"codex", "claude", "antigravity"}
    if (cwd / ".cursor").exists() or (cwd / ".cursorrules").exists():
        tools.add("cursor")
    if (cwd / ".windsurf").exists() or (cwd / ".windsurfrules").exists():
        tools.add("windsurf")
    if (cwd / ".zencoder").exists():
        tools.add("zencoder")
    if (cwd / "GEMINI.md").exists() or (cwd / ".idx" / "airules.md").exists():
        tools.add("gemini")
    if (cwd / ".github" / "copilot-instructions.md").exists():
        tools.add("copilot")
    if (cwd / "CLAUDE.md").exists() or (cwd / ".claude").exists():
        tools.add("claude")
    return sorted(tools)


def _detect_priorities(cwd: Path, app_type: str) -> list[str]:
    priorities = ["maintainability", "verification"]
    if (cwd / "tests").exists():
        priorities.insert(0, "testability")
    if (cwd / ".github" / "workflows").exists():
        priorities.append("automation")
    if app_type in {"api-service", "fullstack-app"}:
        priorities.append("speed")
    return list(dict.fromkeys(priorities))


def _infer_project_profile(cwd: Path) -> dict:
    languages = _detect_languages(cwd)
    frameworks = _detect_frameworks(cwd)
    package_manager = _detect_package_manager(cwd)
    build_commands, test_commands = _detect_commands(cwd, package_manager)
    app_type = _detect_app_type(cwd, frameworks, languages)
    return {
        "idea": "Project using skillsmith",
        "project_stage": _detect_project_stage(cwd),
        "app_type": app_type,
        "languages": languages,
        "frameworks": frameworks,
        "package_manager": package_manager,
        "deployment_target": _detect_deployment_target(cwd, frameworks),
        "priorities": _detect_priorities(cwd, app_type),
        "target_tools": _detect_target_tools(cwd),
        "allow_remote_skills": False,
        "trusted_skill_sources": ["local"],
        "allowed_remote_domains": ["github.com", "skills.sh"],
        "blocked_skill_sources": [],
        "require_pinned_github_refs": True,
        "trusted_publisher_keys": {},
        "trusted_publisher_public_keys": {},
        "publisher_verification_mode": "optional",
        "publisher_signature_scheme_mode": "auto",
        "publisher_signature_algorithms": ["hmac-sha256", "rsa-sha256"],
        "publisher_key_rotation": {},
        "min_remote_trust_score": 65,
        "min_remote_freshness_score": 0,
        "required_remote_licenses": [],
        "build_commands": build_commands,
        "test_commands": test_commands,
    }


def _merge_profile(existing: dict, inferred: dict) -> dict:
    merged = dict(existing)
    derived_fields = [
        "project_stage",
        "app_type",
        "languages",
        "frameworks",
        "package_manager",
        "deployment_target",
        "priorities",
        "target_tools",
        "build_commands",
        "test_commands",
    ]
    for field in derived_fields:
        merged[field] = inferred[field]

    for field, default in {
        "idea": inferred.get("idea", "Project using skillsmith"),
        "allow_remote_skills": False,
        "trusted_skill_sources": ["local"],
        "allowed_remote_domains": ["github.com", "skills.sh"],
        "blocked_skill_sources": [],
        "require_pinned_github_refs": True,
        "trusted_publisher_keys": {},
        "trusted_publisher_public_keys": {},
        "publisher_verification_mode": "optional",
        "publisher_signature_scheme_mode": "auto",
        "publisher_signature_algorithms": ["hmac-sha256", "rsa-sha256"],
        "publisher_key_rotation": {},
        "min_remote_trust_score": 65,
        "min_remote_freshness_score": 0,
        "required_remote_licenses": [],
    }.items():
        merged.setdefault(field, default)
    return merged


def _prompt_list(prompt_label: str, default_items: list[str]) -> list[str]:
    default_text = ", ".join(default_items)
    raw = click.prompt(prompt_label, default=default_text, show_default=True)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _prompt_optional_list(prompt_label: str, default_items: list[str] | None = None) -> list[str]:
    default_items = default_items or []
    default_text = ", ".join(default_items)
    raw = click.prompt(prompt_label, default=default_text, show_default=bool(default_text))
    return [item.strip() for item in raw.split(",") if item.strip() and item.strip().lower() != "none"]


def _format_list(values: list[str], fallback: str = "none") -> str:
    cleaned = [value for value in values if value and value.lower() != "none"]
    return ", ".join(cleaned) if cleaned else fallback


def _format_publisher_keys(value: dict | list | None) -> str:
    keys = _normalize_publisher_keys(value or {})
    return _format_list(list(keys.keys()))


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


def _format_publisher_public_keys(value: dict | list | None) -> str:
    keys = _normalize_publisher_public_keys(value or {})
    return _format_list(list(keys.keys()))


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


def _collect_guided_profile(cwd: Path) -> dict:
    profile = _infer_project_profile(cwd)
    console.print("\n[bold cyan]🚀 Skillsmith Guided Interview (Phase 2)[/bold cyan]")
    console.print("[dim]This helps us customize your .agent architecture for your specific project.[/dim]\n")

    # Group 1: Product Strategy
    console.print("[bold yellow]1. Product Strategy[/bold yellow]")
    profile["idea"] = Prompt.ask("What are you building?", default=profile.get("idea", "Project using skillsmith"))
    profile["project_stage"] = Prompt.ask("Project stage", choices=["greenfield", "existing", "maintenance"], default=profile.get("project_stage", "existing"))
    profile["app_type"] = Prompt.ask("App type", choices=["application", "library", "web-app", "api-service", "fullstack-app", "cli-tool"], default=profile.get("app_type", "application"))
    console.print("")

    # Group 2: Technical Stack
    console.print("[bold yellow]2. Technical Stack[/bold yellow]")
    profile["languages"] = _prompt_list("Languages (comma-separated)", profile.get("languages", ["python"]))
    profile["frameworks"] = _prompt_list("Frameworks (comma-separated)", profile.get("frameworks", ["none"]))
    profile["package_manager"] = Prompt.ask("Package manager", choices=["pip", "uv", "npm", "yarn", "pnpm", "poetry", "go", "cargo", "maven", "gradle"], default=profile.get("package_manager", "pip"))
    profile["deployment_target"] = Prompt.ask("Deployment target", default=profile.get("deployment_target", "not-specified"))
    console.print("")

    # Group 3: Engineering Priorities
    console.print("[bold yellow]3. Engineering Priorities[/bold yellow]")
    profile["priorities"] = _prompt_list("Priorities (comma-separated)", profile.get("priorities", ["maintainability", "verification"]))
    profile["target_tools"] = _prompt_list("Tools targeted (claude, cursor...)", profile.get("target_tools", ["claude"]))
    console.print("")

    # Group 4: Governance & Trust (The $100M Layer)
    console.print("[bold blue]4. Governance & Trust Layer[/bold blue]")
    profile["allow_remote_skills"] = Confirm.ask("Allow remote skill discovery from GitHub/Registry?", default=bool(profile.get("allow_remote_skills", False)))
    
    if profile["allow_remote_skills"]:
        profile["trusted_skill_sources"] = _prompt_list("Trusted sources", ["local", "github", "skills.sh"])
    else:
        profile["trusted_skill_sources"] = ["local"]

    profile["require_pinned_github_refs"] = Confirm.ask("Require commit-pinned GitHub refs for security?", default=True)
    
    profile["publisher_verification_mode"] = Prompt.ask(
        "Publisher verification stringency",
        choices=["off", "optional", "required"],
        default=profile.get("publisher_verification_mode", "optional")
    )

    console.print("\n[bold green]Gathering advanced configurations...[/bold green]")
    # Maintain raw data collection for expert fields
    raw_trusted_publisher_public_keys = Prompt.ask(
        "Trusted publisher public keys (key_id=modulus:exponent)",
        default=", ".join(
            f"{k}={v['n']}:{v.get('e', 65537)}"
            for k, v in _normalize_publisher_public_keys(profile.get("trusted_publisher_public_keys", {})).items()
        ) or "none"
    )
    profile["trusted_publisher_public_keys"] = _parse_publisher_public_keys((raw_trusted_publisher_public_keys,))

    raw_trusted_publisher_keys = Prompt.ask(
        "Trusted publisher keys (key_id=secret)",
        default=", ".join(f"{k}={v}" for k, v in _normalize_publisher_keys(profile.get("trusted_publisher_keys", {})).items()) or "none"
    )
    profile["trusted_publisher_keys"] = _normalize_publisher_keys((raw_trusted_publisher_keys,))

    profile["min_remote_trust_score"] = int(Prompt.ask("Minimum remote trust score (0-100)", default=str(profile.get("min_remote_trust_score", 65))))
    profile["min_remote_freshness_score"] = int(Prompt.ask("Minimum remote freshness (0-100)", default="0"))

    return profile


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _render_project_context(cwd: Path, profile: dict) -> str:
    top_level = sorted(item.name for item in cwd.iterdir() if item.name not in {".git", ".venv", "__pycache__"})
    lines = [
        "# Project Context",
        "",
        "## Summary",
        f"- Idea: {profile['idea']}",
        f"- Stage: {profile['project_stage']}",
        f"- App type: {profile['app_type']}",
        f"- Package manager: {profile['package_manager']}",
        f"- Deployment target: {profile['deployment_target']}",
        "",
        "## Languages",
    ]
    lines.extend([f"- {language}" for language in profile["languages"]])
    lines.extend(["", "## Frameworks"])
    lines.extend([f"- {framework}" for framework in profile["frameworks"]] or ["- none-detected"])
    lines.extend(
        [
            "",
            "## Commands",
            f"- Build: {', '.join(profile['build_commands'])}",
            f"- Test: {', '.join(profile['test_commands'])}",
            "",
            "## Priorities",
        ]
    )
    lines.extend([f"- {priority}" for priority in profile["priorities"]])
    lines.extend(["", "## Target Tools"])
    lines.extend([f"- {tool}" for tool in profile["target_tools"]])
    lines.extend(["", "## Skill Policy"])
    lines.append(f"- Allow remote skills: {str(profile['allow_remote_skills']).lower()}")
    lines.append(f"- Trusted sources: {_format_list(profile['trusted_skill_sources'])}")
    lines.append(f"- Allowed remote domains: {_format_list(profile.get('allowed_remote_domains', ['github.com', 'skills.sh']))}")
    lines.append(f"- Blocked sources: {_format_list(profile['blocked_skill_sources'])}")
    lines.append(
        "- Require pinned GitHub refs: "
        + ("true" if profile.get("require_pinned_github_refs", True) else "false")
    )
    lines.append(f"- Trusted publisher keys: {_format_publisher_keys(profile.get('trusted_publisher_keys', {}))}")
    lines.append(
        f"- Trusted publisher public keys: {_format_publisher_public_keys(profile.get('trusted_publisher_public_keys', {}))}"
    )
    lines.append(f"- Publisher verification mode: {profile.get('publisher_verification_mode', 'optional')}")
    lines.append(f"- Publisher signature scheme mode: {profile.get('publisher_signature_scheme_mode', 'auto')}")
    lines.append(
        f"- Allowed publisher signature algorithms: {', '.join(_publisher_signature_algorithms(profile.get('publisher_signature_algorithms', [])))}"
    )
    lines.append(f"- Publisher key rotation: {_format_key_rotation(profile.get('publisher_key_rotation', {}))}")
    lines.append(f"- Minimum remote trust: {profile['min_remote_trust_score']}")
    lines.append(f"- Minimum remote freshness: {profile['min_remote_freshness_score']}")
    lines.append(f"- Required remote licenses: {_format_list(profile['required_remote_licenses'])}")
    lines.extend(["", "## Top-Level Files"])
    lines.extend([f"- {name}" for name in top_level[:40]])
    return "\n".join(lines) + "\n"


def _write_project_artifacts(cwd: Path, agents_dir: Path, profile: dict) -> None:
    _write_yaml(agents_dir / "project_profile.yaml", profile)
    context_dir = agents_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "project-context.md").write_text(_render_project_context(cwd, profile), encoding="utf-8")


def _copy_platform_files(cwd: Path) -> None:
    marker = "<!-- Skillsmith -->"
    if not PLATFORM_DIR.exists():
        return

    for platform_name, paths in PLATFORM_FILES.items():
        src_file = PLATFORM_DIR / paths["src"]
        dest_file = cwd / paths["dest"]
        if not src_file.exists():
            continue

        src_content = src_file.read_text(encoding="utf-8")
        if dest_file.exists():
            existing = dest_file.read_text(encoding="utf-8")
            if marker in existing:
                console.print(f"[dim][SKIP][/dim] {paths['dest']} (already has Skillsmith config)")
                continue
            with open(dest_file, "a", encoding="utf-8") as handle:
                handle.write(f"\n\n{marker}\n{src_content}")
            console.print(f"[green][OK][/green] Appended Skillsmith config to {paths['dest']} ({platform_name})")
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "w", encoding="utf-8") as handle:
            handle.write(f"{marker}\n{src_content}")
        console.print(f"[green][OK][/green] Created {paths['dest']} ({platform_name})")


def _copy_agent_templates(cwd: Path, minimal: bool, all_skills: bool, category: str | None, tag: str | None, bundle: str | None = None) -> None:
    agents_dir = cwd / ".agent"
    agents_dir.mkdir(exist_ok=True)
    template_agents_dir = TEMPLATE_DIR / ".agent"
    if not template_agents_dir.exists():
        return

    for item in template_agents_dir.iterdir():
        if item.name == "skills":
            continue
        dest = agents_dir / item.name
        if item.is_dir():
            if not dest.exists():
                shutil.copytree(item, dest)
                console.print(f"[green][OK][/green] Created .agent/{item.name}/")
            else:
                for subitem in item.iterdir():
                    if subitem.is_file() and not (dest / subitem.name).exists():
                        shutil.copy(subitem, dest / subitem.name)
                        console.print(f"[green][OK][/green] Added {subitem.name} to .agent/{item.name}/")
        else:
            if not dest.exists():
                shutil.copy(item, dest)
                console.print(f"[green][OK][/green] Created .agent/{item.name}")

    if minimal:
        return

    # Scaffold advanced directories (parity with ECC/CCG)
    for folder_name in ["principles", "hooks", "scripts", "snapshots"]:
        folder = agents_dir / folder_name
        if not folder.exists():
            folder.mkdir(exist_ok=True)
            readme = folder / "README.md"
            if not readme.exists():
                readme.write_text(f"# .agent/{folder_name}\n\nThis directory contains project-specific {folder_name} for AI agents.\n", encoding="utf-8")
            console.print(f"[green][OK][/green] Scaffolded {folder_name}/ (advanced layer)")

    # Ecosystem Siphon Logic (v1.0.1)
    # 1. First, attempt to siphon advanced contents from the ecosystem if requested
    if all_skills or bundle or (category and category not in ["core", "essentials"]):
        _siphon_from_ecosystem(agents_dir, bundle, category, tag)
    
    # 2. Local Fallback/Primary Core
    src_skills_dir = TEMPLATE_DIR / ".agent" / "skills"
    if src_skills_dir.exists():
        _copy_local_skills(agents_dir, src_skills_dir, minimal, all_skills, category, tag, bundle)
    else:
        console.print("[dim][INFO][/dim] Local template skills not found. Using Siphon Hub fallback.")

def _siphon_from_ecosystem(agents_dir: Path, bundle: str | None, category: str | None, tag: str | None) -> None:
    """Delegates content acquisition to the Antigravity Awesome Skills ecosystem (npx)."""
    try:
        cmd = ["npx", "-y", "antigravity-awesome-skills@latest", "--path", str(agents_dir / "skills")]
        
        # Mapping bundle/category/tag to npx args if ecosystem supports them
        # Note: awesome-skills CLI currently takes --tag for versions, but we can pass names.
        if bundle:
            console.print(f"[blue][INFO][/blue] Siphoning bundle: [bold]{bundle}[/bold] from ecosystem...")
        elif category:
            console.print(f"[blue][INFO][/blue] Siphoning category: [bold]{category}[/bold] from ecosystem...")
            
        # We run it synchronously to ensure skills are present before finishing init
        import subprocess
        subprocess.run(cmd, check=True, capture_output=True)
        console.print("[green][OK][/green] Ecosystem siphon complete.")
    except Exception as e:
        console.print(f"[yellow][WARN][/yellow] Ecosystem siphon failed: {e}")
        console.print("[dim]Falling back to local core templates...[/dim]")

def _copy_local_skills(agents_dir: Path, src_skills_dir: Path, minimal: bool, all_skills: bool, category: str | None, tag: str | None, bundle: str | None = None) -> None:
    """Directly copy skills from local template directory."""
    catalog = load_catalog()
    catalog_map = {item["name"]: item for item in catalog if "name" in item} if catalog else {}
    
    installed_count = 0
    for skill_path in src_skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
            
        skill_name = skill_path.name
        should_include = False
        
        if not all_skills and not category and not tag:
            should_include = skill_name in CORE_SKILLS
        elif all_skills:
            should_include = True
        elif category:
            skill_data = catalog_map.get(skill_name)
            should_include = bool(skill_data and skill_data.get("category") == category)
        elif tag:
            skill_data = catalog_map.get(skill_name)
            should_include = bool(skill_data and tag.lower() in [item.lower() for item in skill_data.get("tags", [])])

        if should_include:
            dest_skill_dir = agents_dir / "skills" / skill_name
            if not dest_skill_dir.exists():
                shutil.copytree(skill_path, dest_skill_dir)
                console.print(f"[blue][INFO][/blue] Added local skill: {skill_name}")
                installed_count += 1

    if installed_count == 0 and not minimal:
        console.print("[dim]No matching local skills found for current filters.[/dim]")


def _install_recommended_skills(cwd: Path, profile: dict, limit: int = 3) -> list[dict]:
    dest_dir = cwd / ".agent" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    explained_candidates = explain_recommendations_for_profile(profile, cwd, limit=limit)

    for candidate, explanation in explained_candidates:
        target = dest_dir / candidate.name
        if target.exists():
            continue
        candidate.metadata = {
            **(candidate.metadata or {}),
            "recommendation": {
                "reasons": explanation["reasons"],
                "matched_query": explanation["matched_query"],
                "matched_profile": explanation["matched_profile"],
            },
        }

        src_dir = find_template_skill_dir(candidate.name)
        if src_dir:
            shutil.copytree(src_dir, target)
            record_skill_install(cwd, candidate, target)
            installed.append({"name": candidate.name, "reasons": explanation["reasons"]})
            continue

        install_url = candidate_install_url(candidate)
        if install_url and profile.get("allow_remote_skills"):
            allowed_domains = {
                str(item).strip().lower()
                for item in profile.get("allowed_remote_domains", ["github.com", "skills.sh"])
                if str(item).strip()
            }
            host = (urlparse(install_url).hostname or "").lower()
            if not host or not (host in allowed_domains or any(host.endswith("." + domain) for domain in allowed_domains)):
                continue
            if profile.get("require_pinned_github_refs", True):
                match = re.search(r"github\.com/[^/]+/[^/]+/(tree|blob)/([^/]+)/.+", install_url)
                if match:
                    ref = match.group(2)
                    if not re.fullmatch(r"[0-9a-f]{40}", ref, flags=re.IGNORECASE):
                        continue
            try:
                download_github_dir(install_url, target)
                record_skill_install(cwd, candidate, target)
                installed.append({"name": candidate.name, "reasons": explanation["reasons"]})
            except Exception:
                continue

    return installed


@click.command()
@click.option("--minimal", is_flag=True, help="Create minimal structure without optional skills")
@click.option("--guided", is_flag=True, help="Run an interview-driven setup and save a project profile")
@click.option("--auto-install", is_flag=True, help="Install recommended skills from the project profile")
@click.option("--agents-md-only", is_flag=True, help="Only create AGENTS.md")
@click.option("--all", "all_skills", is_flag=True, help="Install ALL available skills (warning: large)")
@click.option("--category", help="Install all skills from a specific category (e.g., 'data-ai')")
@click.option("--bundle", help="Target a specific ecosystem bundle (e.g. 'python-pro', 'web-wizard').")
@click.option("--template", help="Initialize from a high-performance project template (e.g., 'fastapi-pro', 'nextjs-pro')")
@click.option("--tag", help="Install all all skills with a specific tag (e.g., 'python')")
@click.argument("directory", required=False, type=click.Path(file_okay=False, dir_okay=True, path_type=Path), default=".")
def init_command(minimal, guided, auto_install, agents_md_only, all_skills, category, bundle, tag, template, directory):
    """Initialize .agent and tool-native instruction structure."""
    cwd = directory.resolve() if directory else Path.cwd()
    cwd.mkdir(parents=True, exist_ok=True)

    if template:
        skeleton_dir = Path(__file__).parent.parent / "templates" / "skeletons" / template
        if not skeleton_dir.exists():
            console.print(f"[red][ERROR][/red] Template '{template}' not found in {skeleton_dir}")
            return
        
        console.print(f"[cyan][INFO][/cyan] Initializing from template '{template}'...")
        # Copy skeleton content as root project files
        for item in skeleton_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, cwd / item.name, dirs_exist_ok=True)
            else:
                shutil.copy(item, cwd / item.name)
        console.print(f"[green][OK][/green] Scaffolded {template} files.")

    agents_md = cwd / "AGENTS.md"
    if not agents_md.exists():
        template_agents_md = TEMPLATE_DIR / "AGENTS.md"
        if template_agents_md.exists():
            shutil.copy(template_agents_md, agents_md)
            console.print("[green][OK][/green] Created AGENTS.md")
        else:
            with open(agents_md, "w", encoding="utf-8") as handle:
                handle.write(
                    "# AGENTS.md\n\n> This file provides AI coding agents with context about this project.\n\n"
                    "## Project Overview\n\n## Setup Commands\n\n## Testing Workflows\n\n## Coding Style\n"
                )
            console.print("[green][OK][/green] Created AGENTS.md (default template)")

    _copy_platform_files(cwd)

    if agents_md_only:
        return

    _copy_agent_templates(cwd, minimal, all_skills, category, tag, bundle)
    agents_dir = cwd / ".agent"
    profile = _collect_guided_profile(cwd) if guided else _infer_project_profile(cwd)
    _write_project_artifacts(cwd, agents_dir, profile)
    render_all(cwd, profile)
    installed = []
    if auto_install or guided:
        installed = _install_recommended_skills(cwd, profile)
    console.print("[green][OK][/green] Wrote .agent/project_profile.yaml")
    console.print("[green][OK][/green] Wrote .agent/context/project-context.md")
    console.print("[green][OK][/green] Aligned managed files from project profile")
    if installed:
        console.print("[green][OK][/green] Installed recommended skills:")
        for item in installed:
            console.print(f"  - {item['name']}: {'; '.join(item['reasons'][:2])}")
    console.print("\n[bold green]Successfully initialized .agent structure![/bold green]")
