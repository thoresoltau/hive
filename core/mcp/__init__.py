"""MCP (Model Context Protocol) client implementation for Hive Agent Swarm."""

from .protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPToolSchema,
    MCPToolResult,
    MCPResource,
    MCPResourceContent,
)
from .client import MCPClient
from .manager import MCPClientManager
from .config import MCPServerConfig

__all__ = [
    # Protocol
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "MCPToolSchema",
    "MCPToolResult",
    "MCPResource",
    "MCPResourceContent",
    # Client
    "MCPClient",
    "MCPClientManager",
    "MCPServerConfig",
]
