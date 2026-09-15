"""renfield-mcp-weather — MCP server for Open-Meteo weather API."""

__version__ = "1.1.0"

from .server import mcp


def main():
    """Entry point for the MCP server."""
    mcp.run()
