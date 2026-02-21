import os
import zipfile
import datetime
from pathlib import Path
import click
from . import console

@click.command()
@click.option("--note", help="Memo to save with the snapshot")
@click.option("--list", "list_snapshots", is_flag=True, help="List all available snapshots")
@click.option("--restore", help="Snapshot filename to restore")
def snapshot_command(note, list_snapshots, restore):
    """Save or restore a snapshot of your .agent/ context."""
    cwd = Path.cwd()
    snap_dir = cwd / ".agent" / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    if list_snapshots:
        console.print("[bold cyan]Available Snapshots:[/bold cyan]")
        for snap in sorted(snap_dir.glob("*.zip"), reverse=True):
            console.print(f"  {snap.name} [dim]({snap.stat().st_size // 1024} KB)[/dim]")
        return

    if restore:
        snap_path = snap_dir / restore
        if not snap_path.exists():
            console.print(f"[red]Error: Snapshot {restore} not found.[/red]")
            return
        
        import shutil
        agents_dir = cwd / ".agent"
        # Backup current skills? No, just extract.
        with zipfile.ZipFile(snap_path, 'r') as z:
            z.extractall(agents_dir)
        console.print(f"[green][OK][/green] Restored snapshot: {restore}")
        return

    # Create new snapshot
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    name = f"snap_{timestamp}.zip"
    snap_path = snap_dir / name
    
    with zipfile.ZipFile(snap_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(cwd / ".agent"):
            if "snapshots" in root: continue
            for file in files:
                fpath = Path(root) / file
                arcname = fpath.relative_to(cwd / ".agent")
                z.write(fpath, arcname)
    
    console.print(f"[green][OK][/green] Saved snapshot to .agent/snapshots/{name}")
    if note:
        (snap_dir / f"{name}.note.txt").write_text(note)
