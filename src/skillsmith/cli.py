import os
import shutil
import click
import requests
import re
import yaml
import json
import zipfile
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

TEMPLATE_DIR = Path(__file__).parent / "templates"
PLATFORM_DIR = TEMPLATE_DIR / "platforms"

# Platform-specific rule files that each AI tool auto-reads
PLATFORM_FILES = {
    "gemini": {"src": "GEMINI.md", "dest": "GEMINI.md"},
    "claude": {"src": "CLAUDE.md", "dest": "CLAUDE.md"},
    "cursor": {"src": ".cursorrules", "dest": ".cursorrules"},
    "cursor_mdc": {"src": ".cursor/rules/skillsmith.mdc", "dest": ".cursor/rules/skillsmith.mdc"},
    "windsurf": {"src": ".windsurfrules", "dest": ".windsurfrules"},
    "copilot": {"src": ".github/copilot-instructions.md", "dest": ".github/copilot-instructions.md"},
}

CORE_SKILLS = [
    "software_lifecycle",
    "prompt_engineering",
    "how_to_research",
    "how_to_create_skills",
    "how_to_create_implementation_plan",
    "code_review",
    "debugging",
    "git_workflow",
    "software_architecture",
    "ui_ux_design",
]


def iter_skill_dirs(base_dir: Path):
    """Yield skill directories containing SKILL.md, recursively."""
    if not base_dir.exists():
        return
    for skill_md in sorted(base_dir.rglob("SKILL.md")):
        if skill_md.is_file():
            yield skill_md.parent


def find_template_skill_dir(skill_name: str):
    """Find a template skill directory by folder name, recursively."""
    skills_root = TEMPLATE_DIR / ".agent" / "skills"
    exact = skills_root / skill_name
    if (exact / "SKILL.md").exists():
        return exact

    matches = [d for d in iter_skill_dirs(skills_root) if d.name == skill_name]
    if len(matches) == 1:
        return matches[0]
    return None

def load_catalog():
    """Loads the skill catalog JSON if available."""
    catalog_path = TEMPLATE_DIR / ".agent" / "skill_catalog.json"
    
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
                if isinstance(catalog, dict) and "total_skills" not in catalog:
                    catalog["total_skills"] = len(catalog.get("skills", {}))
                return catalog
        except Exception:
            return None
    return None

def validate_skill(skill_path):
    """Validates a skill directory structure and metadata."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "Missing SKILL.md"
    
    try:
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return False, "Missing YAML frontmatter start (---)"
            
        parts = content.split("---")
        if len(parts) < 3:
            return False, "Incomplete YAML frontmatter (missing closing ---)"
        
        metadata = yaml.safe_load(parts[1])
        if not metadata:
            return False, "Empty or invalid YAML frontmatter"
            
        required = ["name", "description", "version"]
        missing = [key for key in required if key not in metadata]
        if missing:
            return False, f"Missing required keys: {', '.join(missing)}"
            
        return True, "Valid"
    except Exception as e:
        return False, f"Parse error: {str(e)}"


def validate_skill_agentskills(skill_path):
    """Validates a skill against the AgentSkills.io open standard.
    
    Returns (is_valid: bool, messages: list[str])
    Messages are warnings/errors — empty list means fully compliant.
    """
    skill_md = skill_path / "SKILL.md"
    errors = []
    warnings = []

    if not skill_md.exists():
        return False, ["[red]FAIL[/red] Missing SKILL.md"]

    try:
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return False, ["[red]FAIL[/red] Missing YAML frontmatter"]

        parts = content.split("---")
        if len(parts) < 3:
            return False, ["[red]FAIL[/red] Incomplete YAML frontmatter"]

        meta = yaml.safe_load(parts[1]) or {}

        # ── Required fields ───────────────────────────────────────────────────
        for field in ["name", "description", "version"]:
            if field not in meta:
                errors.append(f"[red]missing '{field}'[/red]")

        # ── Description quality ───────────────────────────────────────────────
        desc = meta.get("description", "")
        if desc and len(desc) < 10:
            errors.append("[red]description too short (<10 chars)[/red]")
        elif desc and len(desc) > 200:
            warnings.append("[yellow]description >200 chars (trim for context efficiency)[/yellow]")

        # ── Version format (semver) ───────────────────────────────────────────
        ver = str(meta.get("version", ""))
        if ver and not re.match(r"^\d+\.\d+\.\d+$", ver):
            errors.append(f"[red]version '{ver}' not semver (e.g. 1.0.0)[/red]")

        # ── Recommended optional fields ───────────────────────────────────────
        if "tags" not in meta:
            warnings.append("[yellow]missing 'tags' (recommended for discovery)[/yellow]")
        if "globs" not in meta:
            warnings.append("[yellow]missing 'globs' (recommended for file-scoped rules)[/yellow]")

        # ── Body content check ────────────────────────────────────────────────
        body = "---".join(parts[2:]).strip()
        if len(body) < 50:
            errors.append("[red]SKILL.md body too short (<50 chars)[/red]")

        # ── Optional scripts/ directory ───────────────────────────────────────
        scripts_dir = skill_path / "scripts"
        # Not required, but note if present
        # (no warning if absent — it's optional)

        is_valid = len(errors) == 0
        all_messages = errors + warnings
        return is_valid, all_messages

    except Exception as e:
        return False, [f"[red]Parse error: {str(e)}[/red]"]


def download_github_dir(repo_url, dest_dir):
    """Downloads a directory from GitHub using the API."""
    # Pattern: https://github.com/OWNER/REPO/tree/BRANCH/PATH
    match = re.search(r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)", repo_url)
    if not match:
        # Try raw content pattern or simpler repo/path
        match = re.search(r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", repo_url)
        
    if not match:
        console.print("[red]Error: Invalid GitHub directory URL.[/red]")
        console.print("Expected: https://github.com/OWNER/REPO/tree/BRANCH/PATH")
        return False

    owner, repo, branch, path = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        items = response.json()
        
        # Check if the response is a list (directory contents)
        if not isinstance(items, list):
            console.print(f"[red]Error: URL must point to a directory, not a file.[/red]")
            return False

        dest_dir.mkdir(parents=True, exist_ok=True)
        
        with console.status(f"[bold blue]Downloading skill files...") as status:
            for item in items:
                if item["type"] == "file":
                    file_url = item["download_url"]
                    file_path = dest_dir / item["name"]
                    # Download file content
                    file_resp = requests.get(file_url)
                    file_resp.raise_for_status()
                    with open(file_path, "wb") as f:
                        f.write(file_resp.content)
                elif item["type"] == "dir":
                    # We only support shallow folders for now
                    pass
        
        # Verify if it's a valid skill
        if not (dest_dir / "SKILL.md").exists():
            console.print(f"[yellow]Warning: Downloaded folder does not contain SKILL.md.[/yellow]")
            
        return True
    except requests.exceptions.HTTPError as he:
        console.print(f"[red]GitHub API Error: {he.response.status_code} - {he.response.reason}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Download failed: {str(e)}[/red]")
        return False

@click.group()
def main():
    """Agentic Skills Library CLI"""
    pass

@main.command()
@click.option("--minimal", is_flag=True, help="Create minimal structure without optional skills")
@click.option("--agents-md-only", is_flag=True, help="Only create AGENTS.md")
@click.option("--all", "all_skills", is_flag=True, help="Install ALL available skills (warning: large)")
@click.option("--category", help="Install all skills from a specific category (e.g., 'data-ai')")
@click.option("--tag", help="Install all skills with a specific tag (e.g., 'python')")
def init(minimal, agents_md_only, all_skills, category, tag):
    """Initialize .agent and AGENTS.md structure"""
    cwd = Path.cwd()
    
    # 1. Handle AGENTS.md
    agents_md = cwd / "AGENTS.md"
    if not agents_md.exists():
        template_agents_md = TEMPLATE_DIR / "AGENTS.md"
        if template_agents_md.exists():
            shutil.copy(template_agents_md, agents_md)
            console.print("[green][OK][/green] Created AGENTS.md")
        else:
            # Fallback inline template
            with open(agents_md, "w") as f:
                f.write("# AGENTS.md\n\n> This file provides AI coding agents with context about this project.\n\n## Project Overview\n\n## Setup Commands\n\n## Testing Workflows\n\n## Coding Style\n")
            console.print("[green][OK][/green] Created AGENTS.md (default template)")

    # 1b. Handle platform-specific rule files (append if exists, create if not)
    SKILLSMITH_MARKER = "<!-- Skillsmith -->"
    if PLATFORM_DIR.exists():
        for platform_name, paths in PLATFORM_FILES.items():
            src_file = PLATFORM_DIR / paths["src"]
            dest_file = cwd / paths["dest"]
            if not src_file.exists():
                continue
            
            src_content = src_file.read_text(encoding="utf-8")
            
            if dest_file.exists():
                existing = dest_file.read_text(encoding="utf-8")
                if SKILLSMITH_MARKER in existing:
                    console.print(f"[dim][SKIP][/dim] {paths['dest']} (already has Skillsmith config)")
                    continue
                # Append our content to existing file
                with open(dest_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{SKILLSMITH_MARKER}\n{src_content}")
                console.print(f"[green][OK][/green] Appended Skillsmith config to {paths['dest']} ({platform_name})")
            else:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(f"{SKILLSMITH_MARKER}\n{src_content}")
                console.print(f"[green][OK][/green] Created {paths['dest']} ({platform_name})")
    
    if agents_md_only:
        return

    # 2. Handle .agent folder
    agents_dir = cwd / ".agent"
    agents_dir.mkdir(exist_ok=True)
    
    template_agents_dir = TEMPLATE_DIR / ".agent"
    if template_agents_dir.exists():
        # Copy everything EXCEPT skills (handled separately)
        for item in template_agents_dir.iterdir():
            if item.name == "skills":
                continue
                
            dest = agents_dir / item.name
            if item.is_dir():
                # For directories like guides, plans, workflows: 
                # mkdir and copy contents (or copytree if not exists)
                if not dest.exists():
                    shutil.copytree(item, dest)
                    console.print(f"[green][OK][/green] Created .agent/{item.name}/")
                else:
                    # If folder exists, copy individual files (don't overwrite whole folder)
                    for subitem in item.iterdir():
                        if subitem.is_file() and not (dest / subitem.name).exists():
                            shutil.copy(subitem, dest / subitem.name)
                            console.print(f"[green][OK][/green] Added {subitem.name} to .agent/{item.name}/")
            else:
                # For files like prd.md, status.md
                if not dest.exists():
                    shutil.copy(item, dest)
                    console.print(f"[green][OK][/green] Created .agent/{item.name}")
        
        # 3. Handle skills (unless minimal)
        if not minimal:
            src_skills_zip = template_agents_dir / "skills.zip"
            dest_skills_dir = agents_dir / "skills"
            
            if src_skills_zip.exists():
                catalog = load_catalog()
                catalog_skills = catalog.get("skills", {}) if catalog else {}
                
                with zipfile.ZipFile(src_skills_zip, 'r') as z:
                    files_to_extract = []
                    extracted_skills = set()
                    skill_files = []

                    for file_path in z.namelist():
                        normalized = file_path.replace("\\", "/")
                        parts = [p for p in normalized.split("/") if p]
                        if len(parts) < 3 or parts[0] != "skills":
                            continue
                        if parts[-1] != "SKILL.md":
                            continue
                        skill_name = parts[-2]
                        skill_files.append((file_path, skill_name))

                    default_mode = not all_skills and not category and not tag
                    has_core_skills = any(name in CORE_SKILLS for _, name in skill_files)

                    for file_path, skill_name in skill_files:
                        should_include = False

                        # 1. Core Set (Default)
                        if default_mode:
                            should_include = skill_name in CORE_SKILLS or not has_core_skills
                        # 2. --all flag
                        elif all_skills:
                            should_include = True
                        # 3. --category flag
                        elif category:
                            skill_data = catalog_skills.get(skill_name)
                            if skill_data and skill_data.get("category") == category:
                                should_include = True
                        # 4. --tag flag
                        elif tag:
                            skill_data = catalog_skills.get(skill_name)
                            if skill_data and tag.lower() in skill_data.get("tags", []):
                                should_include = True

                        if should_include:
                            files_to_extract.append(file_path)
                            extracted_skills.add(skill_name)
                    
                    if files_to_extract:
                        for member in files_to_extract:
                            normalized = member.replace("\\", "/")
                            parts = [p for p in normalized.split("/") if p]
                            dest_path = agents_dir.joinpath(*parts)
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(dest_path, "wb") as dst:
                                dst.write(src.read())
                        for s in sorted(extracted_skills):
                            console.print(f"[blue][INFO][/blue] Added skill: {s}")
    
    console.print("\n[bold green]Successfully initialized .agent structure![/bold green]")

@main.command(name="list")
@click.option("--category", help="Filter by category")
@click.option("--tag", help="Filter by tag")
@click.option("--list-categories", is_flag=True, help="Show all available categories")
def list_skills(category, tag, list_categories):
    """List available portable skills (optional specific filters)"""
    
    catalog = load_catalog()
    
    if list_categories:
        if catalog:
            console.print("[bold cyan]Available Categories:[/bold cyan]")
            for cat in catalog.get("categories", []):
                console.print(f"- {cat}")
            console.print("\n[bold cyan]Top Tags (Try --tag <name>):[/bold cyan]")
            # Just show a few common ones as hints
            common_tags = ["python", "react", "security", "seo", "agent", "aws"]
            for t in common_tags:
                console.print(f"- {t}")
        else:
            console.print("[red]Catalog not found. Cannot list categories.[/red]")
        return

    skills_dir = TEMPLATE_DIR / ".agent" / "skills"
    if not skills_dir.exists():
        console.print("[red]Error: Templates not found.[/red]")
        return
        
    title = "Available Skills"
    if category: title += f" (Category: {category})"
    if tag: title += f" (Tag: {tag})"
    
    table = Table(title=title)
    table.add_column("Skill", style="cyan")
    table.add_column("Description", style="white")
    
    for skill_folder in iter_skill_dirs(skills_dir):
        skill_md = skill_folder / "SKILL.md"

        # Filter logic for list
        if category or tag:
            if catalog:
                skill_data = catalog["skills"].get(skill_folder.name)
                if not skill_data:
                    continue
                if category and skill_data.get("category") != category:
                    continue
                if tag and tag.lower() not in skill_data.get("tags", []):
                    continue

        description = "No description found"
        if skill_md.exists():
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
                if "description:" in content:
                    for line in content.split("\n"):
                        if "description:" in line:
                            description = line.split("description:")[1].strip()
                            break
        table.add_row(skill_folder.name, description)
            
    console.print(table)

@main.command()
@click.argument("name_or_url")
def add(name_or_url):
    """Add a skill from local library or GitHub URL"""
    dest_dir = Path.cwd() / ".agent" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if name_or_url.startswith("http"):
        # Remote GitHub Add
        skill_name = name_or_url.split("/")[-1]
        dest_skill = dest_dir / skill_name
        
        if dest_skill.exists():
            console.print(f"[yellow]Skill '{skill_name}' already exists.[/yellow]")
            return
            
        if download_github_dir(name_or_url, dest_skill):
            console.print(f"[green][OK][/green] Successfully added remote skill: {skill_name}")
    else:
        # Local Add
        skill_name = name_or_url
        src_skill = find_template_skill_dir(skill_name)
        
        if src_skill is None:
            console.print(f"[red]Error: Skill '{skill_name}' not found in local library.[/red]")
            return
            
        dest_skill = dest_dir / skill_name
        if dest_skill.exists():
            console.print(f"[yellow]Skill '{skill_name}' already exists.[/yellow]")
            return
            
        shutil.copytree(src_skill, dest_skill)
        console.print(f"[green][OK][/green] Added skill: {skill_name}")

@main.command()
@click.option("--local", is_flag=True, help="Lint local template library")
@click.option("--spec", default="basic", type=click.Choice(["basic", "agentskills"], case_sensitive=False),
              help="Validation spec: basic (default) or agentskills (AgentSkills.io standard)")
def lint(local, spec):
    """Validate skill structures and metadata"""
    if local:
        skills_dir = TEMPLATE_DIR / ".agent" / "skills"
    else:
        skills_dir = Path.cwd() / ".agent" / "skills"
        
    if not skills_dir.exists():
        console.print(f"[red]Error: Skills directory not found at {skills_dir}[/red]")
        return

    spec_label = "AgentSkills.io Standard" if spec == "agentskills" else "Basic"
    table = Table(title=f"Skill Lint Results [{spec_label}]: {skills_dir}")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="white")
    
    all_passed = True
    for skill_folder in iter_skill_dirs(skills_dir):
        if spec == "agentskills":
            is_valid, messages = validate_skill_agentskills(skill_folder)
            status = "[green]PASS[/green]" if is_valid else "[red]FAIL[/red]"
            detail = "  |  ".join(messages) if messages else "Fully compliant"
        else:
            is_valid, detail = validate_skill(skill_folder)
            status = "[green]PASS[/green]" if is_valid else "[red]FAIL[/red]"

        table.add_row(skill_folder.name, status, detail)
        if not is_valid:
            all_passed = False
                
    console.print(table)
    if spec == "agentskills":
        console.print("\n[dim]AgentSkills.io spec: https://agentskills.io — adopted by Anthropic, Microsoft, OpenAI, Google[/dim]")
    if not all_passed:
        exit(1)

@main.command()
@click.argument("goal")
@click.option("--max-skills", default=7, show_default=True, help="Max number of skills to include")
@click.option("--output", default=None, help="Output file path (default: .agent/workflows/<goal-slug>.md)")
def compose(goal, max_skills, output):
    """Generate a workflow by composing relevant skills for a given GOAL.
    
    Example: skillsmith compose "build a saas mvp"
    """
    cwd = Path.cwd()
    skills_dir = cwd / ".agent" / "skills"

    if not skills_dir.exists():
        console.print("[red]Error: .agent/skills/ not found. Run: skillsmith init[/red]")
        return

    # ── Load all skills and their metadata ───────────────────────────────────
    goal_words = set(re.sub(r"[^a-z0-9 ]", "", goal.lower()).split())

    scored = []
    for skill_folder in iter_skill_dirs(skills_dir):
        skill_md = skill_folder / "SKILL.md"

        try:
            content = skill_md.read_text(encoding="utf-8")
            parts = content.split("---")
            meta = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
            meta = meta or {}

            name = meta.get("name", skill_folder.name)
            desc = meta.get("description", "")
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            # Score: keyword overlap between goal and (name + desc + tags + body)
            searchable = f"{name} {desc} {' '.join(tags)} {'---'.join(parts[2:])}"
            searchable_words = set(re.sub(r"[^a-z0-9 ]", "", searchable.lower()).split())
            score = len(goal_words & searchable_words)

            if score > 0:
                scored.append({
                    "folder": skill_folder.name,
                    "name": name,
                    "desc": desc,
                    "score": score,
                })
        except Exception:
            continue

    if not scored:
        console.print(f"[yellow]No skills matched the goal: '{goal}'[/yellow]")
        console.print("Try broader keywords, or run: skillsmith list")
        return

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    selected = scored[:max_skills]

    # ── Generate workflow markdown ────────────────────────────────────────────
    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")
    if output:
        out_path = Path(output)
    else:
        workflows_dir = cwd / ".agent" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        out_path = workflows_dir / f"{slug}.md"

    lines = [
        f"# Workflow: {goal.title()}",
        f"",
        f"> Auto-generated by `skillsmith compose` from {len(selected)} skills.",
        f"> Edit this file to customize the workflow for your project.",
        f"",
        f"---",
        f"",
    ]

    for i, skill in enumerate(selected, 1):
        lines += [
            f"## Step {i}: {skill['name'].replace('-', ' ').title()}",
            f"",
            f"**Skill:** `{skill['folder']}`",
            f"",
            f"**Purpose:** {skill['desc']}",
            f"",
            f"**Instructions:** See `.agent/skills/{skill['folder']}/SKILL.md`",
            f"",
            f"### Acceptance Criteria",
            f"- [ ] Step {i} complete",
            f"",
            f"---",
            f"",
        ]

    lines += [
        f"## Notes",
        f"",
        f"- Generated for goal: **{goal}**",
        f"- Skills matched by keyword relevance (score-ranked)",
        f"- Add or remove steps as needed for your project",
        f"",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")

    # ── Print summary ─────────────────────────────────────────────────────────
    console.print(f"\n[bold cyan]Composing workflow for:[/bold cyan] {goal}\n")
    table = Table(title=f"Selected Skills ({len(selected)} of {len(scored)} matched)", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Skill", style="cyan")
    table.add_column("Relevance", justify="center")
    table.add_column("Description", style="white")

    for i, skill in enumerate(selected, 1):
        bar = "#" * min(skill["score"], 10)
        table.add_row(str(i), skill["folder"], f"[green]{bar}[/green]", skill["desc"][:60] + ("..." if len(skill["desc"]) > 60 else ""))

    console.print(table)
    console.print(f"\n[green][OK][/green] Workflow saved to: [bold]{out_path}[/bold]")
    console.print(f"[dim]Edit the file to customize steps and acceptance criteria.[/dim]\n")


@main.command()
@click.option("--fix", is_flag=True, help="Auto-fix missing platform files by running init")
def doctor(fix):
    """Check your skillsmith setup health across all AI platforms."""
    cwd = Path.cwd()
    SKILLSMITH_MARKER = "<!-- Skillsmith -->"
    all_ok = True

    console.print("\n[bold cyan][ DOCTOR ] Skillsmith Doctor[/bold cyan]\n")

    # ── 1. Core files ────────────────────────────────────────────────────────
    console.print("[bold]Core Files[/bold]")
    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        console.print("  [green][OK][/green] AGENTS.md found")
    else:
        console.print("  [red][!!][/red] AGENTS.md missing  ->  run: [bold]skillsmith init[/bold]")
        all_ok = False

    # ── 2. Platform rule files ────────────────────────────────────────────────
    console.print("\n[bold]Platform Rule Files[/bold]")
    platform_labels = {
        "gemini":     ("GEMINI.md",                         "Gemini CLI"),
        "claude":     ("CLAUDE.md",                         "Claude Code"),
        "cursor":     (".cursorrules",                      "Cursor (legacy)"),
        "cursor_mdc": (".cursor/rules/skillsmith.mdc",      "Cursor (modern .mdc)"),
        "windsurf":   (".windsurfrules",                    "Windsurf"),
        "copilot":    (".github/copilot-instructions.md",   "GitHub Copilot"),
    }
    for key, (dest, label) in platform_labels.items():
        dest_path = cwd / dest
        if dest_path.exists():
            content = dest_path.read_text(encoding="utf-8", errors="ignore")
            if SKILLSMITH_MARKER in content:
                console.print(f"  [green][OK][/green] {dest} ({label})")
            else:
                console.print(f"  [yellow][!!][/yellow] {dest} exists but missing Skillsmith config  ->  run: [bold]skillsmith init[/bold]")
                all_ok = False
        else:
            console.print(f"  [red][!!][/red] {dest} missing ({label})  ->  run: [bold]skillsmith init[/bold]")
            all_ok = False

    # ── 3. GSD State files ────────────────────────────────────────────────────
    console.print("\n[bold]State Files (.agent/)[/bold]")
    import time
    state_files = {
        "PROJECT.md": "Tech stack & vision",
        "ROADMAP.md": "Strategic milestones",
        "STATE.md":   "Current task context (read FIRST each session)",
    }
    for fname, desc in state_files.items():
        fpath = cwd / ".agent" / fname
        if fpath.exists():
            age_hours = (time.time() - fpath.stat().st_mtime) / 3600
            if fname == "STATE.md" and age_hours > 24:
                console.print(f"  [yellow][!!][/yellow] .agent/{fname} is stale ({age_hours:.0f}h old) -- update it to prevent context rot")
                all_ok = False
            else:
                console.print(f"  [green][OK][/green] .agent/{fname}  [dim]({desc})[/dim]")
        else:
            console.print(f"  [red][!!][/red] .agent/{fname} missing  ->  run: [bold]skillsmith init[/bold]")
            all_ok = False

    # ── 4. Skills ─────────────────────────────────────────────────────────────
    console.print("\n[bold]Skills[/bold]")
    skills_dir = cwd / ".agent" / "skills"
    if skills_dir.exists():
        valid = sum(1 for _ in iter_skill_dirs(skills_dir))
        invalid = 0
        console.print(f"  [green][OK][/green] {valid} skills installed", end="")
        if invalid:
            console.print(f"  [yellow]({invalid} missing SKILL.md)[/yellow]")
        else:
            console.print()
    else:
        console.print("  [red][!!][/red] .agent/skills/ not found  ->  run: [bold]skillsmith init[/bold]")
        all_ok = False

    # ── 5. Platform detection ─────────────────────────────────────────────────
    console.print("\n[bold]Platform Detection[/bold]")
    # Detect which tools are likely active based on env vars / known config dirs
    detections = {
        "Gemini CLI":      (cwd / "GEMINI.md").exists() or (Path.home() / ".gemini").exists(),
        "Claude Code":     (cwd / "CLAUDE.md").exists() or (Path.home() / ".claude").exists(),
        "Cursor":          (cwd / ".cursorrules").exists() or (cwd / ".cursor").exists(),
        "Windsurf":        (cwd / ".windsurfrules").exists() or (cwd / ".windsurf").exists(),
        "GitHub Copilot":  (cwd / ".github" / "copilot-instructions.md").exists(),
    }
    for platform, detected in detections.items():
        icon = "[green][OK][/green]" if detected else "[dim] - [/dim]"
        console.print(f"  {icon} {platform}")

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    if all_ok:
        console.print("[bold green][OK] All checks passed! Your skillsmith setup is healthy.[/bold green]")
    else:
        console.print("[bold yellow][!!] Some issues found. Run [bold]skillsmith init[/bold] to fix missing files.[/bold yellow]")
        if fix:
            console.print("\n[cyan]Running skillsmith init to fix issues...[/cyan]")
            from click.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(init, [])
            console.print(result.output)
    console.print()


@main.command()
def budget():
    """Analyze context token budget across all platform files and skills."""
    cwd = Path.cwd()

    # Official limits from each vendor's docs
    PLATFORM_LIMITS = {
        "GEMINI.md":                        {"tokens": 2000,  "label": "Gemini CLI",      "unit": "tokens",  "warn_pct": 0.75},
        "CLAUDE.md":                        {"tokens": 1500,  "label": "Claude Code",     "unit": "tokens",  "warn_pct": 0.75},
        ".cursorrules":                     {"tokens": 2000,  "label": "Cursor (legacy)", "unit": "tokens",  "warn_pct": 0.75},
        ".cursor/rules/skillsmith.mdc":     {"tokens": 2000,  "label": "Cursor (.mdc)",   "unit": "tokens",  "warn_pct": 0.75},
        ".windsurfrules":                   {"chars": 6000,   "label": "Windsurf",        "unit": "chars",   "warn_pct": 0.80},
        ".github/copilot-instructions.md":  {"tokens": 4000,  "label": "Copilot",         "unit": "tokens",  "warn_pct": 0.75},
    }
    STATE_FILES = [
        ".agent/STATE.md",
        ".agent/PROJECT.md",
        ".agent/ROADMAP.md",
        "AGENTS.md",
    ]

    def estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token (GPT/Claude standard)."""
        return max(1, len(text) // 4)

    console.print("\n[bold cyan][ BUDGET ] Context Budget Report[/bold cyan]\n")

    # ── Platform files ────────────────────────────────────────────────────────
    table = Table(title="Platform Rule Files", show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Platform", style="white")
    table.add_column("Size", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Usage", justify="right")
    table.add_column("Status", justify="center")

    total_tokens = 0
    for dest, limits in PLATFORM_LIMITS.items():
        fpath = cwd / dest
        if not fpath.exists():
            table.add_row(dest, limits["label"], "-", "-", "-", "[dim]not found[/dim]")
            continue

        content = fpath.read_text(encoding="utf-8", errors="ignore")
        unit = limits["unit"]

        if unit == "chars":
            size = len(content)
            limit = limits["chars"]
            pct = size / limit
            size_str = f"{size:,} chars"
            limit_str = f"{limit:,} chars"
        else:
            size = estimate_tokens(content)
            limit = limits["tokens"]
            pct = size / limit
            size_str = f"~{size:,} tokens"
            limit_str = f"{limit:,} tokens"
            total_tokens += size

        pct_str = f"{pct*100:.0f}%"
        if pct >= 1.0:
            status = "[bold red][!!] OVER LIMIT[/bold red]"
        elif pct >= limits["warn_pct"]:
            status = "[yellow][!!] WARNING[/yellow]"
        else:
            status = "[green][OK][/green]"

        table.add_row(dest, limits["label"], size_str, limit_str, pct_str, status)

    console.print(table)

    # ── State / context files ─────────────────────────────────────────────────
    console.print()
    state_table = Table(title="Agent Context Files (.agent/)", show_header=True, header_style="bold magenta")
    state_table.add_column("File", style="cyan")
    state_table.add_column("Tokens", justify="right")
    state_table.add_column("Recommendation")

    for rel in STATE_FILES:
        fpath = cwd / rel
        if not fpath.exists():
            state_table.add_row(rel, "-", "[dim]not found[/dim]")
            continue
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        tokens = estimate_tokens(content)
        total_tokens += tokens
        if tokens > 2000:
            rec = "[yellow]Consider splitting into sub-files[/yellow]"
        elif tokens < 50:
            rec = "[yellow]Very short — add more context[/yellow]"
        else:
            rec = "[green]Good[/green]"
        state_table.add_row(rel, f"~{tokens:,}", rec)

    console.print(state_table)

    # ── Skills budget ─────────────────────────────────────────────────────────
    skills_dir = cwd / ".agent" / "skills"
    if skills_dir.exists():
        skill_tokens = 0
        skill_count = 0
        for d in skills_dir.iterdir():
            skill_md = d / "SKILL.md"
            if skill_md.exists():
                skill_tokens += estimate_tokens(skill_md.read_text(encoding="utf-8", errors="ignore"))
                skill_count += 1
        console.print(f"\n[bold]Skills:[/bold] {skill_count} skills  (~{skill_tokens:,} tokens total if all loaded at once)")
        console.print(f"  [dim]Tip: Skills are loaded on-demand - only active skills consume context.[/dim]")
        total_tokens += skill_tokens

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(f"\n[bold]Total estimated context load:[/bold] ~{total_tokens:,} tokens")
    RECOMMENDED_MAX = 8000
    if total_tokens > RECOMMENDED_MAX:
        console.print(f"[bold red][!!] Exceeds recommended max of {RECOMMENDED_MAX:,} tokens.[/bold red]")
        console.print("   Consider: removing unused skills, shortening STATE.md, or splitting large files.")
    else:
        bar_filled = int((total_tokens / RECOMMENDED_MAX) * 20)
        bar = "#" * bar_filled + "-" * (20 - bar_filled)
        pct = total_tokens / RECOMMENDED_MAX * 100
        console.print(f"[green]Budget:[/green] [{bar}] {pct:.0f}% of {RECOMMENDED_MAX:,} token recommended max")
    console.print()


@main.command()
@click.option("--force", is_flag=True, help="Overwrite modified skills")
def update(force):
    project_skills_dir = Path.cwd() / ".agent" / "skills"
    template_skills_dir = TEMPLATE_DIR / ".agent" / "skills"
    
    if not project_skills_dir.exists():
        console.print("[red]Error: .agent/skills not found in current directory.[/red]")
        return
        
    table = Table(title="Skill Update Status")
    table.add_column("Skill", style="cyan")
    table.add_column("Action", style="bold")
    table.add_column("Details", style="white")
    
    for skill_folder in iter_skill_dirs(project_skills_dir):
            
        skill_name = skill_folder.name
        relative = skill_folder.relative_to(project_skills_dir)
        template_skill = template_skills_dir / relative
        if not template_skill.exists():
            fallback = find_template_skill_dir(skill_name)
            template_skill = fallback if fallback else template_skill
        
        if not template_skill.exists():
            table.add_row(skill_name, "[yellow]SKIP[/yellow]", "Not found in library")
            continue
            
        local_md = skill_folder / "SKILL.md"
        tpl_md = template_skill / "SKILL.md"
        
        if not local_md.exists() or not tpl_md.exists():
            table.add_row(skill_name, "[red]ERROR[/red]", "Missing SKILL.md")
            continue
            
        try:
            local_text = local_md.read_text(encoding="utf-8")
            tpl_text = tpl_md.read_text(encoding="utf-8")
            
            local_parts = local_text.split("---")
            tpl_parts = tpl_text.split("---")
            
            if len(local_parts) < 3:
                # Local file is corrupted or modified beyond recognition
                if not force:
                    table.add_row(skill_name, "[blue]PENDING[/blue]", "Local SKILL.md has no frontmatter (Modified, use --force)")
                    continue
                local_ver = "0.0.0"
            else:
                local_meta = yaml.safe_load(local_parts[1]) or {}
                local_ver = local_meta.get("version", "0.0.0")
                
            tpl_meta = yaml.safe_load(tpl_parts[1]) or {}
            tpl_ver = tpl_meta.get("version", "0.0.0")
            
            if local_ver < tpl_ver:
                if local_text != tpl_text and not force:
                    table.add_row(skill_name, "[blue]PENDING[/blue]", f"{local_ver} -> {tpl_ver} (Modified, use --force)")
                else:
                    # Update
                    if skill_folder.exists():
                        shutil.rmtree(skill_folder)
                    shutil.copytree(template_skill, skill_folder)
                    table.add_row(skill_name, "[green]UPGRADED[/green]", f"{local_ver} -> {tpl_ver}")
            else:
                table.add_row(skill_name, "[dim]OK[/dim]", f"Up to date ({local_ver})")
        except Exception as e:
            table.add_row(skill_name, "[red]FAIL[/red]", str(e))
            
    console.print(table)


@main.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    show_default=True,
    help="Transport: stdio (Claude Code/Cursor) or http (browser/HTTP clients)",
)
@click.option("--host", default="localhost", show_default=True, help="Host for HTTP transport")
@click.option("--port", default=47731, show_default=True, help="Port for HTTP transport")
def serve(transport, host, port):
    """Start the skillsmith MCP server for AI tool integration.

    Exposes your .agent/skills/ library as an MCP server so Claude Code,
    Cursor, Windsurf, and Gemini CLI can query skills on-demand.

    \b
    Tools exposed:
      list_skills      - list all installed skills
      get_skill        - read full SKILL.md for a specific skill
      search_skills    - keyword search across all skills
      compose_workflow - generate a workflow for a goal

    \b
    Examples:
      skillsmith serve                    # stdio (add to Claude Code / Cursor)
      skillsmith serve --transport http   # HTTP on localhost:3333

    \b
    Claude Code integration:
      claude mcp add skillsmith -- skillsmith serve

    \b
    Cursor integration (add to .cursor/mcp.json):
      {
        "mcpServers": {
          "skillsmith": {
            "command": "skillsmith",
            "args": ["serve"]
          }
        }
      }
    """
    try:
        from skillsmith.mcp_server import run_server
    except ImportError as e:
        if "mcp" in str(e).lower():
            console.print("[red]Error: MCP package not installed.[/red]")
            console.print("Install it with: [bold]pip install skillsmith[mcp][/bold]")
            console.print("Or: [bold]pip install mcp[/bold]")
            return
        raise

    skills_dir = Path.cwd() / ".agent" / "skills"
    if not skills_dir.exists():
        console.print("[yellow]Warning: .agent/skills/ not found in current directory.[/yellow]")
        console.print("Run [bold]skillsmith init[/bold] first, or cd to your project root.")

    if transport == "http":
        console.print(f"\n[bold cyan]skillsmith MCP Server[/bold cyan] (HTTP)")
        console.print(f"Listening on: [bold]http://{host}:{port}/mcp[/bold]")
        console.print(f"Skills dir:   [dim]{skills_dir}[/dim]")
        console.print(f"\nAdd to Claude Code: [dim]claude mcp add --transport http skillsmith http://{host}:{port}/mcp[/dim]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]\n")
    else:
        # stdio — no console output, the protocol uses stdin/stdout
        import sys
        if sys.stderr.isatty():
            import sys as _sys
            print(f"[skillsmith MCP] Starting stdio server. Skills: {skills_dir}", file=_sys.stderr)

    run_server(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()
