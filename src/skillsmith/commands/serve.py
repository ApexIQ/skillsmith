import click
from . import console

@click.command()
@click.option("--transport", default="stdio", help="MCP transport (stdio or sse)")
@click.option("--host", default="localhost", help="SSE host")
@click.option("--port", default=8000, help="SSE port")
def serve_command(transport, host, port):
    """Start the skillsmith MCP server for AI tool integration."""
    from ..mcp_server import serve_mcp
    serve_mcp(transport, host, port)
