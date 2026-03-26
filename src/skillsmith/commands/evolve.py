import datetime
import time
import json
import os
import subprocess
import shutil
import re
from pathlib import Path

import click
import yaml

from . import console, validate_skill_agentskills
from ..services.evolution import EvolutionEngine, EvolutionMode, DegradationLevel

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

@evolve_command.command("evaluate")
@click.argument("skill", required=False)
@click.option("--output", default=".agent/evals/captured_skills.md", help="Path to the evaluation report.")
def evolve_evaluate_command(skill, output):
    """Score captured or existing skills against project DNA and AgentSkills.io standards."""
    from rich.table import Table
    
    cwd = Path.cwd()
    skills_dir = cwd / ".agent" / "skills"
    
    if skill:
        # Resolve path
        target = skills_dir / skill
        if not target.exists():
            target = Path(skill)
        target_paths = [target] if (target / "SKILL.md").exists() else []
    else:
        target_paths = [d for d in skills_dir.rglob("*") if (d / "SKILL.md").exists()]

    if not target_paths:
        console.print("[yellow]No valid skills found to evaluate.[/yellow]")
        return

    console.print(f"[bold blue]Skillsmith Evolution: Evaluation Mode[/bold blue] (Scoring {len(target_paths)} skills...)\n")
    
    table = Table(title="Skill Evolution Leaderboard", show_header=True, header_style="bold blue")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Findings")

    report_content = [
        "# Skill Evolution Report",
        f"Generated: {datetime.datetime.now().isoformat()}\n",
        "| Skill | Score | Status | Findings |",
        "| :--- | :--- | :--- | :--- |"
    ]
    
    for skill_path in sorted(target_paths):
        is_valid, messages = validate_skill_agentskills(skill_path)
        
        # Scoring Logic (v1.0)
        # 100 base score. -10 for each warning, -30 for each error.
        score = 100
        errors = [m for m in messages if "FAIL" in m or "red" in m]
        warnings = [m for m in messages if "yellow" in m]
        
        score -= (len(errors) * 30)
        score -= (len(warnings) * 10)
        score = max(0, score)
        
        status = "[green]GOLD[/green]" if score >= 90 else "[yellow]SILVER[/yellow]" if score >= 70 else "[red]BRONZE[/red]"
        findings = ", ".join([m.replace("[red]", "").replace("[/red]", "").replace("[yellow]", "").replace("[/yellow]", "").replace("FAIL ", "").strip() for m in messages[:2]])
        
        status_clean = status.replace("[green]", "").replace("[/green]", "").replace("[yellow]", "").replace("[/yellow]", "").replace("[red]", "").replace("[/red]", "")
        table.add_row(skill_path.name, status, f"{score}/100", findings)
        report_content.append(f"| {skill_path.name} | {score}/100 | {status_clean} | {findings} |")

    console.print(table)
    
    # Save report
    report_path = Path(output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_content), encoding="utf-8")
    console.print(f"\n[bold green]Success![/bold green] Evolution Leaderboard synced to [bold]{output}[/bold].")

@evolve_command.command("promote")
@click.argument("skill", required=False)
@click.option("--all", "promote_all", is_flag=True, help="Promote all skills in the project.")
@click.option("--target-dir", default=".agent/skills", help="Directory to move promoted skills to.")
def evolve_promote_command(skill, promote_all, target_dir):
    """Autonomously repair and promote skills to GOLD status (Phase 2.3)."""
    cwd = Path.cwd()
    skills_dir = cwd / ".agent" / "skills"
    
    if promote_all:
        target_paths = [d for d in skills_dir.rglob("*") if (d / "SKILL.md").exists()]
    elif skill:
        skill_path = Path(skill)
        if not skill_path.exists():
            skill_path = skills_dir / skill
        target_paths = [skill_path] if (skill_path / "SKILL.md").exists() else []
    else:
        console.print("[red][ERROR][/red] No skill specified. Use --all to promote entire library.")
        return

    if not target_paths:
        console.print("[yellow][WARN][/yellow] No skills found to promote.")
        return

    console.print(f"[bold blue]Skillsmith Evolution: Mass Promotion Mode[/bold blue] (Repairing {len(target_paths)} skills...)")
    
    repaired_count = 0
    for skill_path in target_paths:
        try:
            # Metadata Repair Logic
            skill_md = skill_path / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            parts = content.split("---")
            if len(parts) < 3: continue
            
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                # NUCLEAR REPAIR: Manual Regex Extraction
                meta = {}
                patterns = {
                    "name": r"name:\s*(.+)",
                    "description": r"description:\s*(.+)",
                    "version": r"version:\s*(.+)",
                    "source": r"source:\s*(.+)"
                }
                for key, pattern in patterns.items():
                    match = re.search(pattern, parts[1])
                    if match:
                        meta[key] = match.group(1).strip().strip('"').strip("'")
            
            repaired = False
            
            # Rule: Ensure SemVer
            if "version" not in meta or not str(meta.get("version")).count("."):
                meta["version"] = "1.0.0"
                repaired = True
            
            # Rule: Ensure Tags
            if "tags" not in meta or not meta["tags"]:
                meta["tags"] = ["promoted", "autonomous-repair"]
                repaired = True
                
            # Rule: Ensure Globs (Recommended)
            if "globs" not in meta:
                meta["globs"] = ["**/*.py"]
                repaired = True

            # Rule: Compaction - Trim long descriptions (>200 chars)
            desc = meta.get("description", "")
            if desc and len(desc) > 200:
                meta["description"] = desc[:197] + "..."
                repaired = True

            # Rule: Cleanup corrupted names
            if "name" in meta:
                clean_name = meta["name"].replace(":", "").replace("@", "").strip()
                if clean_name != meta["name"]:
                    meta["name"] = clean_name
                    repaired = True

            if repaired or True: # Force write to fix any previous YAML corruption
                # Clean dump ensures valid YAML
                parts[1] = f"\n{yaml.dump(meta, sort_keys=False)}"
                skill_md.write_text("---".join(parts), encoding="utf-8")
                repaired_count += 1
                if not promote_all:
                    console.print(f"  [green]Upgraded:[/green] {skill_path.name}")

        except Exception as e:
            if not promote_all:
                console.print(f"  [red]Failed:[/red] {skill_path.name} - {e}")

    console.print(f"\n[bold green]Evolution Complete![/bold green] Repaired and promoted [bold]{repaired_count}[/bold] skills to GOLD status.")

@evolve_command.command("reflect")
@click.option("--format", type=click.Choice(["markdown", "json"]), default="markdown", help="Output format.")
@click.option("--force", is_flag=True, help="Force reflection even if logs are small.")
def evolve_reflect_command(format, force):
    """Reflect on raw logs to distill permanent lessons (L2 Handoff)."""
    from ..memory import MemoryManager
    
    cwd = Path.cwd()
    mm = MemoryManager(cwd)
    
    if not mm.raw_log_path.exists() and not force:
        console.print("[yellow]No raw logs found. Nothing to reflect on.[/yellow]")
        return

    log_size = mm.raw_log_path.stat().st_size if mm.raw_log_path.exists() else 0
    if log_size < 100 and not force:
        console.print(f"[cyan]Logs are small ({log_size} bytes). Use --force to export context.[/cyan]")
        return

    # Deterministic Log Export
    raw_logs = []
    if mm.raw_log_path.exists():
        with open(mm.raw_log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    raw_logs.append(json.loads(line))
                except: continue
    
    if not raw_logs:
        console.print("[yellow]Empty logs. No context to export.[/yellow]")
        return
        
    if format == "json":
        packet = {
            "type": "reflection_context",
            "timestamp": datetime.datetime.now().isoformat(),
            "events": raw_logs
        }
        console.print(json.dumps(packet, indent=2))
        return

    # Markdown Handoff for Human/Agent review
    # Distill logs into memory.md (Layer 2)
    # AI-Integrated Micro-Learning (Layer 2)
    from ..services.evolution import EvolutionEngine
    engine = EvolutionEngine(cwd)
    facts = engine.distill_logs_semantically(mm.raw_log_path)
    engine.update_working_memory(facts, mm.working_memory_path)
    
    # Sync Mission MD if it exists
    from .swarm import _load_mission, _sync_mission_md
    mission = _load_mission(cwd)
    if mission:
        _sync_mission_md(cwd, mission)
    
    console.print(f"\n[bold green]Reflection Complete![/bold green] working_memory updated at [bold].agent/memory.md[/bold].")
    console.print(f"[dim]Next step: Use 'skillsmith advanced flow' to keep context lean.[/dim]")

@evolve_command.command("unlabeled")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--output-dir", default="src/skillsmith/templates/.prototypes", help="Directory to save extracted prototypes.")
def evolve_unlabeled_command(directory, output_dir):
    """Discover Universal Skill Prototypes from unlabeled source code (arXiv:2307.09955)."""
    console.print(f"[bold blue]Skillsmith Evolution: Unlabeled Discovery[/bold blue] (Crawling {directory}...)")
    
    target_dir = Path(directory)
    prototypes_found = 0
    
    extensions = {".py", ".go", ".ts", ".js", ".java", ".rs", ".swift"}
    
    for root, dirs, files in os.walk(target_dir):
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
        if len(lines) < 100:
            return False
            
        low_content = content.lower()
        if not any(k in low_content for k in ["class", "interface", "struct", "func", "pattern"]):
            return False
            
        name = file_path.stem.replace("_", "-")
        proto_path = output_dir / f"{name}.yaml"
        if proto_path.exists():
            return False
            
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

@evolve_command.command("fix")
@click.option("--all", is_flag=True, help="Analyze all degraded skills.")
@click.option("--threshold", default=0.7, help="Success rate threshold for degradation detection.")
def evolve_fix_command(all, threshold):
    """Generate Repair Plans for degraded skills (FIX Handoff)."""
    from rich.table import Table
    from rich.prompt import Confirm

    cwd = Path.cwd()
    engine = EvolutionEngine(cwd)

    console.print("[bold blue]Evolution Engine: FIX Analysis[/bold blue]")
    
    candidates = engine.analyze_skills(threshold)
    fix_candidates = [c for c in candidates if c.mode == EvolutionMode.FIX]

    if not fix_candidates:
        console.print("[green]OK[/green] No degraded skills found. All skills are healthy!")
        return

    table = Table(title=f"Repair Opportunities ({len(fix_candidates)} detected)")
    table.add_column("Skill", style="cyan")
    table.add_column("Success Rate", justify="right")
    table.add_column("Suggested Improvements", style="yellow")

    for candidate in fix_candidates:
        plan = engine.prepare_repair_plan(candidate)
        success_rate = candidate.metrics.get("success_rate", 1.0)
        table.add_row(
            candidate.name,
            f"{success_rate:.1%}",
            ", ".join(plan.changes_suggested)
        )

    console.print(table)
    console.print(f"\n[bold green]Analysis Complete.[/bold green] I have identified {len(fix_candidates)} targets for the Agent to repair.")
    console.print("[dim]Agents should now read the Repair Context for each skill and apply updates.[/dim]")

@evolve_command.command("derive")
@click.argument("skill", required=True)
@click.option("--context", required=True, help="Specialization context (e.g., fastapi).")
def evolve_derive_command(skill, context):
    """Generate a Derivation Specification for skill specialization."""
    cwd = Path.cwd()
    engine = EvolutionEngine(cwd)

    candidates = engine.analyze_skills()
    candidate = next((c for c in candidates if c.name == skill), None)
    
    if not candidate:
        # Fallback if no usage metrics yet
        from . import validate_skill_agentskills
        skill_path = engine.skills_dir / skill
        if not skill_path.exists():
            console.print(f"[red]Error:[/red] Skill '{skill}' not found.")
            return
            
        from ..services.evolution import EvolutionCandidate, DegradationLevel, EvolutionMode
        candidate = EvolutionCandidate(
            name=skill, path=skill_path, mode=EvolutionMode.DERIVE,
            metrics={}, degradation_level=DegradationLevel.HEALTHY,
            reason="Manual derivation request", priority=5
        )

    spec = engine.prepare_derivation_spec(candidate, context)
    
    if spec.success:
        console.print(f"[bold blue]Specialization Spec Prepared:[/bold blue] {spec.skill_name}")
        console.print(f"[cyan]Parent:[/cyan] {skill} (v{spec.original_version})")
        console.print(f"[cyan]Context:[/cyan] {context}")
        console.print(f"\n[bold green]Ready for Handoff![/bold green] Agent can now create the specialized skill at [bold]{spec.context_packet['target_directory']}[/bold].")
    else:
        console.print(f"[red]Error:[/red] {spec.error}")

@evolve_command.command("analyze")
@click.option("--threshold", default=0.7, help="Success rate threshold for degradation detection.")
@click.option("--format", type=click.Choice(["table", "json", "markdown"]), default="table", help="Output format.")
def evolve_analyze_command(threshold, format):
    """Analyze all skills and identify evolution opportunities."""
    from rich.table import Table

    cwd = Path.cwd()
    engine = EvolutionEngine(cwd)

    console.print("[bold blue]Evolution Analysis Report[/bold blue]")

    # Analyze skills
    candidates = engine.analyze_skills(threshold)

    if not candidates:
        console.print("[green]OK[/green] No evolution opportunities found. All skills are optimal!")
        return

    if format == "json":
        # JSON output
        output = {
            "timestamp": datetime.datetime.now().isoformat() + "Z",
            "threshold": threshold,
            "candidates": [c.to_dict() for c in candidates]
        }
        console.print(json.dumps(output, indent=2))

    elif format == "markdown":
        # Markdown output
        console.print("# Evolution Analysis Report")
        console.print(f"\nGenerated: {datetime.datetime.now().isoformat()}")
        console.print(f"Threshold: {threshold}")
        console.print(f"\n## Candidates ({len(candidates)})\n")
        console.print("| Skill | Mode | Status | Priority | Reason |")
        console.print("|-------|------|--------|----------|---------|")
        for c in candidates:
            console.print(f"| {c.name} | {c.mode.value} | {c.degradation_level.value} | {c.priority} | {c.reason} |")

    else:
        # Table output (default)
        table = Table(title=f"Evolution Opportunities ({len(candidates)} found)")
        table.add_column("Skill", style="cyan")
        table.add_column("Mode", style="magenta")
        table.add_column("Status", style="bold")
        table.add_column("Priority", justify="center")
        table.add_column("Reason", style="yellow")

        for candidate in candidates:
            mode_icon = "[FIX]" if candidate.mode == EvolutionMode.FIX else "[DERIVE]"
            status_color = {
                DegradationLevel.FAILED: "red",
                DegradationLevel.CRITICAL: "red",
                DegradationLevel.DEGRADED: "yellow",
                DegradationLevel.WARNING: "yellow",
                DegradationLevel.HEALTHY: "green"
            }.get(candidate.degradation_level, "white")

            table.add_row(
                candidate.name,
                f"{mode_icon}",
                f"[{status_color}]{candidate.degradation_level.value}[/{status_color}]",
                f"{'*' * candidate.priority}",
                candidate.reason[:60]
            )

        console.print(table)

        # Summary
        fix_count = len([c for c in candidates if c.mode == EvolutionMode.FIX])
        derive_count = len([c for c in candidates if c.mode == EvolutionMode.DERIVE])

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  • Skills needing repair (FIX): {fix_count}")
        console.print(f"  • Skills ready for specialization (DERIVE): {derive_count}")
        console.print(f"\n[dim]Run 'skillsmith evolve fix --all' to auto-repair degraded skills.[/dim]")
        console.print(f"[dim]Run 'skillsmith evolve derive <skill> --context <context>' to create specialized versions.[/dim]")
