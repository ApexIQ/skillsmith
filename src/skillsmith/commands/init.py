import shutil
import zipfile
from pathlib import Path
import click
from . import (
    console, 
    TEMPLATE_DIR, 
    PLATFORM_DIR, 
    PLATFORM_FILES, 
    CORE_SKILLS, 
    load_catalog
)

@click.command()
@click.option("--minimal", is_flag=True, help="Create minimal structure without optional skills")
@click.option("--agents-md-only", is_flag=True, help="Only create AGENTS.md")
@click.option("--all", "all_skills", is_flag=True, help="Install ALL available skills (warning: large)")
@click.option("--category", help="Install all skills from a specific category (e.g., 'data-ai')")
@click.option("--tag", help="Install all skills with a specific tag (e.g., 'python')")
def init_command(minimal, agents_md_only, all_skills, category, tag):
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
                # Catalog is a list in v0.6.0+
                catalog_map = {item["name"]: item for item in catalog if "name" in item} if catalog else {}
                
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
                            skill_data = catalog_map.get(skill_name)
                            if skill_data and skill_data.get("category") == category:
                                should_include = True
                        # 4. --tag flag
                        elif tag:
                            skill_data = catalog_map.get(skill_name)
                            if skill_data and tag.lower() in [t.lower() for t in skill_data.get("tags", [])]:
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
