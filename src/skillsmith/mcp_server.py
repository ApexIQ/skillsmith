"""
skillsmith MCP Server
=====================
Exposes your local .agent/skills/ library as an MCP server so any
MCP-compatible AI tool (Claude Code, Cursor, Windsurf, Gemini CLI) can
query skills on-demand — zero context bloat.

Tools exposed:
  - list_skills        : list all installed skills with name, description, tags
  - get_skill          : return full SKILL.md content for a specific skill
  - search_skills      : keyword search across all skills
  - compose_workflow   : generate a workflow from relevant skills for a goal

Usage:
  skillsmith serve                  # stdio (for Claude Code / Cursor)
  skillsmith serve --transport http # HTTP on localhost:3333
  skillsmith serve --port 8080      # custom port
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore


def _load_skill_meta(skill_folder: Path) -> dict:
    """Load metadata from a skill's SKILL.md frontmatter."""
    skill_md = skill_folder / "SKILL.md"
    if not skill_md.exists():
        return {}
    try:
        content = skill_md.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        meta = yaml.safe_load(parts[1]) or {}
        meta["_body"] = parts[2].strip()
        meta["_folder"] = skill_folder.name
        return meta
    except Exception:
        return {}


def _get_skills_dir() -> Path:
    """Find the .agent/skills/ directory from cwd."""
    return Path.cwd() / ".agent" / "skills"


def _iter_skill_dirs(skills_dir: Path):
    """Yield skill directories containing SKILL.md, recursively."""
    if not skills_dir.exists():
        return
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        if skill_md.is_file():
            yield skill_md.parent


def create_mcp_server(skills_dir: Optional[Path] = None) -> "FastMCP":
    """Create and return the configured FastMCP server instance."""
    if FastMCP is None:
        raise ImportError(
            "The 'mcp' package is required for the MCP server.\n"
            "Install it with: pip install skillsmith[mcp]"
        )

    mcp = FastMCP(
        "skillsmith",
        instructions=(
            "This server exposes your local skillsmith skills library. "
            "Use list_skills to discover available skills, get_skill to read "
            "a specific skill's full instructions, search_skills to find skills "
            "by keyword, and compose_workflow to generate a step-by-step workflow "
            "for a given goal."
        ),
    )

    resolved_dir = skills_dir or _get_skills_dir()

    # ── Tool 1: list_skills ───────────────────────────────────────────────────

    @mcp.tool()
    def list_skills() -> list[dict]:
        """List all installed skills with their name, description, and tags.

        Returns a list of skill objects. Use get_skill(name) to read the full
        instructions for any skill.
        """
        results = []
        if not resolved_dir.exists():
            return results
        for folder in _iter_skill_dirs(resolved_dir):
            meta = _load_skill_meta(folder)
            if not meta:
                continue
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            results.append({
                "name": meta.get("name", folder.name),
                "folder": folder.name,
                "description": meta.get("description", ""),
                "version": str(meta.get("version", "")),
                "tags": tags,
            })
        return results

    # ── Tool 2: get_skill ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_skill(name: str) -> str:
        """Get the full SKILL.md content (instructions) for a specific skill.

        Args:
            name: The skill folder name (e.g. 'fastapi_best_practices') or
                  the skill's display name (e.g. 'fastapi-best-practices').
                  Use list_skills() to see all available names.

        Returns:
            The full SKILL.md content including frontmatter and instructions.
        """
        if not resolved_dir.exists():
            return f"Error: Skills directory not found at {resolved_dir}"

        # Try exact folder match first
        exact = resolved_dir / name
        if exact.exists() and (exact / "SKILL.md").exists():
            return (exact / "SKILL.md").read_text(encoding="utf-8")

        # Try slug-normalized match (e.g. "fastapi-best-practices" -> "fastapi_best_practices")
        normalized = re.sub(r"[-\s]+", "_", name.lower())
        for folder in _iter_skill_dirs(resolved_dir):
            if folder.name.lower() == normalized:
                return (folder / "SKILL.md").read_text(encoding="utf-8")

        # Try partial name match
        matches = []
        for folder in _iter_skill_dirs(resolved_dir):
            if name.lower() in folder.name.lower():
                matches.append(folder)

        if len(matches) == 1:
            skill_md = matches[0] / "SKILL.md"
            if skill_md.exists():
                return skill_md.read_text(encoding="utf-8")
        elif len(matches) > 1:
            names = [m.name for m in matches]
            return f"Ambiguous skill name '{name}'. Did you mean one of: {', '.join(names)}?"

        return f"Skill '{name}' not found. Use list_skills() to see available skills."

    # ── Tool 3: search_skills ─────────────────────────────────────────────────

    @mcp.tool()
    def search_skills(query: str, max_results: int = 10) -> list[dict]:
        """Search skills by keyword across name, description, tags, and content.

        Args:
            query: Keywords to search for (e.g. 'testing python backend')
            max_results: Maximum number of results to return (default: 10)

        Returns:
            List of matching skills sorted by relevance score (highest first).
        """
        if not resolved_dir.exists():
            return []

        query_words = set(re.sub(r"[^a-z0-9 ]", "", query.lower()).split())
        if not query_words:
            return []

        scored = []
        for folder in _iter_skill_dirs(resolved_dir):
            meta = _load_skill_meta(folder)
            if not meta:
                continue

            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            searchable = " ".join([
                meta.get("name", ""),
                meta.get("description", ""),
                " ".join(tags),
                meta.get("_body", ""),
            ])
            searchable_words = set(re.sub(r"[^a-z0-9 ]", "", searchable.lower()).split())
            score = len(query_words & searchable_words)

            if score > 0:
                scored.append({
                    "name": meta.get("name", folder.name),
                    "folder": folder.name,
                    "description": meta.get("description", ""),
                    "tags": tags,
                    "relevance_score": score,
                })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:max_results]

    # ── Tool 4: compose_workflow ──────────────────────────────────────────────

    @mcp.tool()
    def compose_workflow(goal: str, max_skills: int = 7) -> str:
        """Generate a step-by-step workflow by composing relevant skills for a goal.

        Args:
            goal: The goal or task description (e.g. 'build a saas mvp',
                  'fix a security vulnerability', 'set up ci/cd pipeline')
            max_skills: Maximum number of skills to include (default: 7)

        Returns:
            A markdown workflow document with numbered steps, one per skill.
        """
        if not resolved_dir.exists():
            return f"Error: Skills directory not found. Run: skillsmith init"

        goal_words = set(re.sub(r"[^a-z0-9 ]", "", goal.lower()).split())
        scored = []

        for folder in _iter_skill_dirs(resolved_dir):
            meta = _load_skill_meta(folder)
            if not meta:
                continue

            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            searchable = " ".join([
                meta.get("name", ""),
                meta.get("description", ""),
                " ".join(tags),
                meta.get("_body", ""),
            ])
            searchable_words = set(re.sub(r"[^a-z0-9 ]", "", searchable.lower()).split())
            score = len(goal_words & searchable_words)

            if score > 0:
                scored.append({
                    "folder": folder.name,
                    "name": meta.get("name", folder.name),
                    "desc": meta.get("description", ""),
                    "score": score,
                })

        if not scored:
            return f"No skills matched the goal: '{goal}'. Try broader keywords."

        scored.sort(key=lambda x: x["score"], reverse=True)
        selected = scored[:max_skills]

        lines = [
            f"# Workflow: {goal.title()}",
            "",
            f"> Generated by skillsmith MCP server from {len(selected)} skills.",
            "> Edit steps as needed for your project.",
            "",
            "---",
            "",
        ]

        for i, skill in enumerate(selected, 1):
            lines += [
                f"## Step {i}: {skill['name'].replace('-', ' ').title()}",
                "",
                f"**Skill:** `{skill['folder']}`",
                "",
                f"**Purpose:** {skill['desc']}",
                "",
                f"**Instructions:** Use get_skill('{skill['folder']}') to read full instructions.",
                "",
                "### Acceptance Criteria",
                f"- [ ] Step {i} complete",
                "",
                "---",
                "",
            ]

        lines += [
            "## Notes",
            "",
            f"- Generated for goal: **{goal}**",
            f"- {len(scored)} skills matched, top {len(selected)} selected by relevance",
            "",
        ]

        return "\n".join(lines)

    return mcp


def run_server(transport: str = "stdio", host: str = "localhost", port: int = 47731) -> None:
    """Start the skillsmith MCP server."""
    mcp = create_mcp_server()

    if transport == "http":
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        # stdio is the default — works with Claude Code, Cursor, Windsurf
        mcp.run(transport="stdio")
