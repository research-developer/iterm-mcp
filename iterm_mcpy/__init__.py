"""Server module for Model Context Protocol (MCP) integration with iTerm2."""

# Lazy import to avoid requiring grpc when only using MCP server
def __getattr__(name):
    if name == "ITermClient":
        from .grpc_client import ITermClient
        return ITermClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['ITermClient']