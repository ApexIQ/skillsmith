import time
from pathlib import Path
import click
from . import console

@click.command()
@click.option("--interval", default=30, help="Polling interval in seconds")
@click.option("--state-file", default=".agent/STATE.md", help="Path to STATE.md")
@click.option("--stale-hours", default=4, help="Warn if STATE.md is older than N hours")
def watch_command(interval, state_file, stale_hours):
    """Watch for context drift and keep your agent state fresh."""
    cwd = Path.cwd()
    state_path = cwd / state_file
    
    def get_branch():
        import subprocess
        try:
            return subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
        except:
            return None

    def get_skill_set():
        skills_dir = cwd / ".agent" / "skills"
        if not skills_dir.exists(): return set()
        return {d.name for d in skills_dir.iterdir() if d.is_dir()}

    def state_age_hours():
        if not state_path.exists(): return 999
        return (time.time() - state_path.stat().st_mtime) / 3600

    last_branch = get_branch()
    last_skills = get_skill_set()
    
    console.print(f"[blue][WATCH][/blue] Monitoring {cwd.name} (interval: {interval}s)")
    
    try:
        while True:
            # 1. Branch Detection
            branch = get_branch()
            if branch and branch != last_branch:
                console.print(f"\n[yellow][DRIFT][/yellow] Branch switched: {last_branch} -> {branch}")
                console.print("[bold]Action:[/bold] Update STATE.md with new branch goals.")
                last_branch = branch
            
            # 2. Skillset changes
            skills = get_skill_set()
            if skills != last_skills:
                diff = skills - last_skills
                if diff:
                    console.print(f"\n[green][NEW][/green] New skills added: {', '.join(diff)}")
                last_skills = skills

            # 3. Staleness check
            age = state_age_hours()
            if age > stale_hours:
                console.print(f"\n[yellow][STALE][/yellow] {state_file} is {age:.1f}h old -- context may be drifting.")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[blue][WATCH][/blue] Stopped.")
