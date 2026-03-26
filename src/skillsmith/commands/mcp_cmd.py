import click
import json
import os
import sys
from pathlib import Path
from . import console

@click.group(name="mcp")
def mcp_group():
    """MCP Operations (Auto-Registration & Tooling)."""
    pass

@mcp_group.command(name="install")
@click.option("--ide", type=click.Choice(["claude", "cursor", "all"]), default="all")
def mcp_install(ide):
    """Automatically register Skillsmith as an MCP server.
    
    This command bridges the gap between your library and your AI IDE (Claude, Cursor). 
    It automatically injects the necessary configuration into your local environment.
    """
    python_exe = sys.executable
    
    # Claude Desktop Registration
    if ide in ("claude", "all"):
        claude_config_path = Path(os.path.expandvars(r"%APPDATA%\Claude\claude_desktop_config.json"))
        try:
            config = {}
            if claude_config_path.exists():
                try:
                    config = json.loads(claude_config_path.read_text(encoding="utf-8"))
                except Exception:
                    config = {}
            
            mcp_servers = config.get("mcpServers", {})
            mcp_servers["skillsmith"] = {
                "command": python_exe,
                "args": ["-m", "skillsmith.mcp_server"]
            }
            config["mcpServers"] = mcp_servers
            
            claude_config_path.parent.mkdir(parents=True, exist_ok=True)
            claude_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            console.print(f"[green][OK][/green] Registered in Claude Desktop: {claude_config_path}")
        except Exception as e:
            console.print(f"[red]Error registering in Claude Desktop:[/red] {e}")

    # Cursor Logic (Instructional)
    if ide in ("cursor", "all"):
        console.print("\n[bold cyan]Cursor Registration (Semi-Automatic):[/bold cyan]")
        console.print("Cursor stores MCP settings in account-sync'd cloud storage.")
        console.print("Add this server in [bold]Settings -> MCP -> Add New MCP Server[/bold]:")
        console.print(f"  [bold]Name:[/bold] Skillsmith")
        console.print(f"  [bold]Type:[/bold] command")
        console.print(f"  [bold]Command:[/bold] {python_exe} -m skillsmith.mcp_server")
        
    console.print("\n[dim]Note: Restart your IDE to apply thermal changes.[/dim]")

@mcp_group.command(name="list")
def mcp_list():
    """List available MCP tools in the Skillsmith universe."""
    from ..mcp_server import create_mcp_server
    mcp = create_mcp_server()
    console.print("\n[bold magenta]Skillsmith MCP Tool Registry:[/bold magenta]")
    for tool in mcp.list_tools():
         console.print(f"  - [green]{tool.name}[/green]: {tool.description}")
