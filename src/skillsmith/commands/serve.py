import click
from . import console

@click.command()
@click.option("--transport", type=click.Choice(["stdio", "http"]), default="stdio", show_default=True, help="MCP transport")
@click.option("--host", default="localhost", help="HTTP host")
@click.option("--port", default=8000, help="HTTP port")
def serve_command(transport, host, port):
    """Start the skillsmith MCP server for AI tool integration."""
    from ..mcp_server import run_server
    run_server(transport, host, port)
