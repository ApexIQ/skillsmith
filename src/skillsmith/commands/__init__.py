import os
import datetime
import sys
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

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
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

def sanitize_json(data):
    """Recursively convert non-serializable objects (like dates) to strings."""
    if isinstance(data, dict):
        return {k: sanitize_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json(i) for i in data]
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data

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
    """Validates a skill against the AgentSkills.io open standard."""
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

        for field in ["name", "description", "version"]:
            if field not in meta:
                errors.append(f"[red]missing '{field}'[/red]")

        desc = meta.get("description", "")
        if desc and len(desc) < 10:
            errors.append("[red]description too short (<10 chars)[/red]")
        elif desc and len(desc) > 200:
            warnings.append("[yellow]description >200 chars (trim for context efficiency)[/yellow]")

        ver = str(meta.get("version", ""))
        if ver and not re.match(r"^\d+\.\d+\.\d+$", ver):
            errors.append(f"[red]version '{ver}' not semver (e.g. 1.0.0)[/red]")

        if "tags" not in meta:
            warnings.append("[yellow]missing 'tags' (recommended for discovery)[/yellow]")
        if "globs" not in meta:
            warnings.append("[yellow]missing 'globs' (recommended for file-scoped rules)[/yellow]")

        body = "---".join(parts[2:]).strip()
        if len(body) < 50:
            errors.append("[red]SKILL.md body too short (<50 chars)[/red]")

        is_valid = len(errors) == 0
        all_messages = errors + warnings
        return is_valid, all_messages

    except Exception as e:
        return False, [f"[red]Parse error: {str(e)}[/red]"]

def download_github_dir(repo_url, dest_dir):
    """Downloads a directory from GitHub using the API."""
    import base64
    repo_match = re.search(r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)", repo_url)
    if not repo_match:
        repo_match = re.search(r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", repo_url)
    
    if not repo_match:
        raise ValueError("Invalid GitHub directory URL")
        
    user, repo, branch, path = repo_match.groups()
    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}?ref={branch}"
    
    response = requests.get(api_url)
    response.raise_for_status()
    items = response.json()
    
    if not isinstance(items, list):
        items = [items]
        
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    for item in items:
        if item["type"] == "file":
            file_path = dest_dir / item["name"]
            content_resp = requests.get(item["url"])
            content_resp.raise_for_status()
            content_data = content_resp.json()
            file_path.write_bytes(base64.b64decode(content_data["content"]))
        elif item["type"] == "dir":
            download_github_dir(f"https://github.com/{user}/{repo}/tree/{branch}/{path}/{item['name']}", dest_dir / item["name"])

# Import commands to expose them
from .init import init_command
from .list_cmd import list_command
from .add import add_command
from .lint import lint_command
from .compose import compose_command
from .doctor import doctor_command
from .budget import budget_command
from .update import update_command
from .rebuild import rebuild_command
from .serve import serve_command
from .snapshot import snapshot_command
from .watch import watch_command
