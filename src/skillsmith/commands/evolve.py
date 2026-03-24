import json
import subprocess
from pathlib import Path
import yaml
import os

import click
from . import console

@click.group(name="evolve")
def evolve_command():
    """Autonomous skill synthesis and library evolution."""
    pass

@evolve_command.command("capture")
@click.option("--limit", default=10, help="Number of recent commits to analyze.")
@click.option("--output-dir", default=".agent/skills/captured", help="Directory to save captured skills.")
def evolve_capture_command(limit, output_dir):
    """Analyze Git history to capture repeatable engineering patterns as draft skills."""
    cwd = Path.cwd()
    if not (cwd / ".git").exists():
        console.print("[red][ERROR][/red] Current directory is not a Git repository.")
        return

    console.print(f"[bold blue]Skillsmith Evolution: Capture Mode[/bold blue] (Analyzing last {limit} commits...)")
    
    try:
        # Get recent commit messages
        result = subprocess.run(
            ["git", "log", f"-n {limit}", "--pretty=format:%h %s"],
            capture_output=True, text=True, check=True
        )
        commits = result.stdout.splitlines()
        
        captured_count = 0
        for commit in commits:
            if not commit.strip():
                continue
            parts = commit.split(" ", 1)
            if len(parts) < 2:
                continue
            hash_id, msg = parts
            
            # Simple heuristic: look for 'fix' or 'feat' or 'refactor'
            tokens = msg.lower().split()
            if any(t in tokens for t in ["fix", "bug", "feat", "refactor", "pattern", "logic"]):
                console.print(f"[cyan]Analyzing:[/cyan] {hash_id} - {msg}")
                _synthesize_skill(hash_id, msg, output_dir)
                captured_count += 1

        if captured_count == 0:
            console.print("[yellow]No repeatable patterns detected in the recent history.[/yellow]")
        else:
            console.print(f"\n[bold green]Success![/bold green] Captured {captured_count} draft skill(s) in {output_dir}.")

    except Exception as e:
        console.print(f"[red][ERROR][/red] Capture failed: {e}")

@evolve_command.command("unlabeled")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--output-dir", default="src/skillsmith/templates/.prototypes", help="Directory to save extracted prototypes.")
def evolve_unlabeled_command(directory, output_dir):
    """Discover Universal Skill Prototypes from unlabeled source code (arXiv:2307.09955)."""
    console.print(f"[bold blue]Skillsmith Evolution: Unlabeled Discovery[/bold blue] (Crawling {directory}...)")
    
    target_dir = Path(directory)
    prototypes_found = 0
    
    # Supported intelligence-rich extensions
    extensions = {".py", ".go", ".ts", ".js", ".java", ".rs", ".swift"}
    
    for root, dirs, files in os.walk(target_dir):
        # Skip hidden and vendor dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "vendor", "dist", "build", "venv"}]
        
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in extensions:
                if _analyze_file_for_prototype(file_path, Path(output_dir)):
                    prototypes_found += 1
                    
    if prototypes_found == 0:
        console.print("[yellow]No universal patterns extracted from this codebase.[/yellow]")
    else:
        console.print(f"\n[bold green]Success![/bold green] Discovered {prototypes_found} Universal Prototype(s) in {output_dir}.")

def _analyze_file_for_prototype(file_path: Path, output_dir: Path) -> bool:
    """Analyze a file for 'Intelligence-rich' structures (XSkill logic)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        # Look for complex patterns: e.g. many classes or deep inheritance or specific decorators
        # Heuristic: file length > 100 AND contains 'class' OR 'interface' OR 'func'
        if len(lines) < 100:
            return False
            
        low_content = content.lower()
        if not any(k in low_content for k in ["class", "interface", "struct", "func", "pattern"]):
            return False
            
        # Extract a draft name
        name = file_path.stem.replace("_", "-")
        proto_path = output_dir / f"{name}.yaml"
        
        if proto_path.exists():
            return False # Avoid duplicates
            
        prototype = {
            "name": name,
            "version": "1.0.0",
            "description": f"Autonomously discovered prototype from {file_path.name}",
            "logic": {
                "discovered_patterns": [
                    f"Analyzed {file_path.suffix} file with {len(lines)} lines.",
                    "Detected high-density logical structures (classes/interfaces).",
                    "Self-evolving agents should prioritize this pattern for similar system designs."
                ],
                "core_implementation_rules": [
                    f"Match the structural integrity of {file_path.name}.",
                    "Ensure separation of concerns as seen in the original source."
                ]
            },
            "embodiments": {
                "claude": [f"Implement with strict type safety as observed in {file_path.name}."],
                "gemini": [f"Use descriptive documentation matching the patterns found in {file_path.name}."]
            }
        }
        
        output_dir.mkdir(parents=True, exist_ok=True)
        proto_path.write_text(yaml.dump(prototype, sort_keys=False), encoding="utf-8")
        console.print(f"  [green]Extracted Prototype:[/green] {proto_path.name}")
        return True
    except Exception:
        return False

def _synthesize_skill(hash_id, commit_msg, output_dir):
    """Simulate skill synthesis from a commit diff."""
    clean_name = "".join(c if c.isalnum() else "_" for c in commit_msg.lower()).strip("_")
    skill_dir = Path(output_dir) / clean_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    (skill_dir / "REF.txt").write_text(f"Source Commit: {hash_id}\nMessage: {commit_msg}", encoding="utf-8")
    skill_md = skill_dir / "SKILL.md"
    
    frontmatter = {
        "name": clean_name.replace("_", "-"),
        "description": f"Captured pattern from commit {hash_id}: {commit_msg}",
        "version": "0.1.0",
        "tags": ["captured", "autonomous"],
        "source": f"git:{hash_id}"
    }
    
    header = "---"
    meta_yml = yaml.dump(frontmatter, sort_keys=False)
    
    body = f"""# {frontmatter['name'].replace('-', ' ').title()}

## Overview
This skill was autonomously captured from commit `{hash_id}`.
Original intent: {commit_msg}

## Captured Logic (Draft)
- [ ] Analyze the diff of `{hash_id}` to extract the specific code transformation.
- [ ] Codify the rule into a repeatable procedure.
- [ ] Ensure this pattern is applied to future tasks with similar goals.

## Usage
Add this skill to your workflow when dealing with `{commit_msg}`.
"""
    
    skill_md.write_text(f"{header}\n{meta_yml}{header}\n\n{body}", encoding="utf-8")
    console.print(f"  [green]Draft generated:[/green] {skill_md.name}")
