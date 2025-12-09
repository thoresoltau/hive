"""MCP Client implementation."""

from typing import Optional, Any
import logging
import uuid

from .protocol import (
    MCPRequest,
    MCPResponse,
    MCPToolSchema,
    MCPToolResult,
    MCPResource,
    MCPResourceContent,
    MCPInitializeResult,
    MCPServerCapabilities,
)
from .config import MCPServerConfig
from .transport import MCPTransport, create_transport

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for communicating with MCP servers.
    
    Usage:
        config = MCPServerConfig(name="context7", transport="http", url="...")
        client = MCPClient(config)
        
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("get_docs", {"library": "react"})
        await client.disconnect()
    """
    
    # MCP Protocol version
    PROTOCOL_VERSION = "2024-11-05"
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._transport: Optional[MCPTransport] = None
        self._initialized = False
        self._server_info: Optional[MCPInitializeResult] = None
        self._capabilities: Optional[MCPServerCapabilities] = None
        self._request_counter = 0
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def is_connected(self) -> bool:
        return self._transport is not None and self._transport.is_connected
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    @property
    def capabilities(self) -> Optional[MCPServerCapabilities]:
        return self._capabilities
    
    def _next_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_counter += 1
        return f"{self.config.name}-{self._request_counter}"
    
    async def connect(self) -> None:
        """Connect to MCP server and initialize."""
        if self.is_connected:
            logger.warning(f"Already connected to {self.name}")
            return
        
        # Create and connect transport
        self._transport = create_transport(self.config)
        await self._transport.connect()
        
        # Initialize MCP session
        await self._initialize()
        
        logger.info(f"MCP client '{self.name}' connected and initialized")
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self._transport:
            await self._transport.disconnect()
            self._transport = None
        
        self._initialized = False
        self._server_info = None
        self._capabilities = None
        
        logger.info(f"MCP client '{self.name}' disconnected")
    
    async def _initialize(self) -> None:
        """Send initialize request to MCP server."""
        request = MCPRequest(
            id=self._next_request_id(),
            method="initialize",
            params={
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {
                    "roots": {"listChanged": True},
                },
                "clientInfo": {
                    "name": "hive-agent-swarm",
                    "version": "1.0.0",
                },
            },
        )
        
        response = await self._send(request)
        
        if response.is_error:
            raise ConnectionError(
                f"Failed to initialize MCP session: {response.error.message}"
            )
        
        self._server_info = MCPInitializeResult(**response.result)
        self._capabilities = self._server_info.capabilities
        self._initialized = True
        
        # Send initialized notification
        await self._notify("notifications/initialized", {})
        
        logger.info(
            f"MCP server '{self._server_info.server_info.name}' "
            f"v{self._server_info.server_info.version} initialized"
        )
    
    async def _send(self, request: MCPRequest) -> MCPResponse:
        """Send request to MCP server."""
        if not self._transport or not self._transport.is_connected:
            raise ConnectionError("Not connected")
        
        return await self._transport.send_with_retry(request)
    
    async def _notify(self, method: str, params: dict) -> None:
        """Send notification (no response expected)."""
        if not self._transport or not self._transport.is_connected:
            return
        
        # Notifications use null id in JSON-RPC
        request = MCPRequest(
            id=0,  # Will be ignored for notifications
            method=method,
            params=params,
        )
        
        # For notifications, we don't wait for response
        # Just send and ignore any response
        try:
            await self._transport.send(request)
        except Exception as e:
            logger.debug(f"Notification {method} failed (ignored): {e}")
    
    # =========================================================================
    # Tool Methods
    # =========================================================================
    
    async def list_tools(self) -> list[MCPToolSchema]:
        """Get list of available tools from server."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect() first.")
        
        if not self._capabilities or not self._capabilities.supports_tools:
            return []
        
        request = MCPRequest(
            id=self._next_request_id(),
            method="tools/list",
        )
        
        response = await self._send(request)
        
        if response.is_error:
            logger.error(f"tools/list failed: {response.error.message}")
            return []
        
        tools_data = response.result.get("tools", [])
        return [MCPToolSchema(**t) for t in tools_data]
    
    async def call_tool(self, name: str, arguments: Optional[dict] = None) -> MCPToolResult:
        """Call a tool on the MCP server."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect() first.")
        
        request = MCPRequest(
            id=self._next_request_id(),
            method="tools/call",
            params={
                "name": name,
                "arguments": arguments or {},
            },
        )
        
        response = await self._send(request)
        
        if response.is_error:
            return MCPToolResult(
                content=[{"type": "text", "text": response.error.message}],
                isError=True,
            )
        
        return MCPToolResult(**response.result)
    
    # =========================================================================
    # Resource Methods
    # =========================================================================
    
    async def list_resources(self) -> list[MCPResource]:
        """Get list of available resources from server."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect() first.")
        
        if not self._capabilities or not self._capabilities.supports_resources:
            return []
        
        request = MCPRequest(
            id=self._next_request_id(),
            method="resources/list",
        )
        
        response = await self._send(request)
        
        if response.is_error:
            logger.error(f"resources/list failed: {response.error.message}")
            return []
        
        resources_data = response.result.get("resources", [])
        return [MCPResource(**r) for r in resources_data]
    
    async def read_resource(self, uri: str) -> Optional[MCPResourceContent]:
        """Read content of a resource."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect() first.")
        
        request = MCPRequest(
            id=self._next_request_id(),
            method="resources/read",
            params={"uri": uri},
        )
        
        response = await self._send(request)
        
        if response.is_error:
            logger.error(f"resources/read failed: {response.error.message}")
            return None
        
        contents = response.result.get("contents", [])
        if contents:
            return MCPResourceContent(**contents[0])
        return None
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    async def ping(self) -> bool:
        """Check if server is responsive."""
        if not self._initialized:
            return False
        
        request = MCPRequest(
            id=self._next_request_id(),
            method="ping",
        )
        
        try:
            response = await self._send(request)
            return not response.is_error
        except Exception:
            return False
    
    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"MCPClient(name={self.name!r}, status={status})"
