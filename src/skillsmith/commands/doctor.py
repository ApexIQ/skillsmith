import shutil
import sys
import time
from pathlib import Path
import click
from . import (
    console, 
    iter_skill_dirs, 
    PLATFORM_FILES
)

@click.command()
@click.option("--fix", is_flag=True, help="Auto-fix missing platform files by running init")
def doctor_command(fix):
    """Check your skillsmith setup health across all AI platforms."""
    cwd = Path.cwd()
    SKILLSMITH_MARKER = "<!-- Skillsmith -->"
    all_ok = True
    # ── 0. PATH Detection ─────────────────────────────────────────────────────
    console.print("[bold]Executable PATH[/bold]")
    is_on_path = shutil.which("skillsmith") is not None
    if is_on_path:
        console.print("  [green][OK][/green] 'skillsmith' command is on your PATH")
    else:
        all_ok = False
        console.print("  [red][!!][/red] 'skillsmith' is NOT on your PATH")
        
        # Try to find where it is
        import sysconfig
        scripts_dir = sysconfig.get_path("scripts")
        if not scripts_dir:
            # Fallback for some systems
            scripts_dir = str(Path(sys.executable).parent / "Scripts")
            
        console.print(f"  [dim]Expected location: {scripts_dir}[/dim]")
        
        if sys.platform == "win32":
            console.print(f"  [yellow]Tip:[/yellow] Run this to fix permanently: [bold]setx PATH \"%PATH%;{scripts_dir}\"[/bold]")
        else:
            console.print(f"  [yellow]Tip:[/yellow] Add this to your shell profile: [bold]export PATH=\"$PATH:{scripts_dir}\"[/bold]")
            
        console.print("  [blue][INFO][/blue] [bold]Alternative:[/bold] You can always use [bold]python -m skillsmith[/bold] to run the tool.")


    console.print("\n[bold cyan][ DOCTOR ] Skillsmith Doctor[/bold cyan]\n")

    # ── 1. Core files ────────────────────────────────────────────────────────
    console.print("[bold]Core Files[/bold]")
    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8", errors="ignore")
        if "Search-then-GSD" in content:
            console.print("  [green][OK][/green] AGENTS.md found (Protocol: Search-then-GSD)")
        else:
            console.print("  [yellow][!!][/yellow] AGENTS.md exists but has legacy GSD protocol  ->  run: [bold]skillsmith init[/bold]")
            all_ok = False
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
            # Import local to avoid circular deps
            from .init import init_command
            from click.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(init_command, [])
            console.print(result.output)
    console.print()
