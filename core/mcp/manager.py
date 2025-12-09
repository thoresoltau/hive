"""MCP Client Manager for handling multiple MCP servers."""

from typing import Optional
import asyncio
import logging
from pathlib import Path

from .client import MCPClient
from .config import MCPServerConfig, load_mcp_config
from .protocol import MCPToolSchema

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages multiple MCP server connections.
    
    Usage:
        manager = MCPClientManager()
        manager.register_server("context7", MCPServerConfig(...))
        
        await manager.connect_all()
        
        tools = await manager.list_all_tools()
        result = await manager.call_tool("context7", "get_docs", {...})
        
        await manager.disconnect_all()
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self._clients: dict[str, MCPClient] = {}
        self._config_path = config_path
    
    @property
    def servers(self) -> list[str]:
        """List of registered server names."""
        return list(self._clients.keys())
    
    @property
    def connected_servers(self) -> list[str]:
        """List of connected server names."""
        return [name for name, client in self._clients.items() if client.is_connected]
    
    def register_server(self, name: str, config: MCPServerConfig) -> None:
        """Register an MCP server configuration."""
        if name in self._clients:
            logger.warning(f"Server '{name}' already registered, replacing")
        
        self._clients[name] = MCPClient(config)
        logger.info(f"Registered MCP server: {name}")
    
    def unregister_server(self, name: str) -> None:
        """Unregister an MCP server."""
        if name in self._clients:
            del self._clients[name]
            logger.info(f"Unregistered MCP server: {name}")
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get client for a specific server."""
        return self._clients.get(name)
    
    def load_from_config(self, config_path: Optional[Path] = None) -> int:
        """
        Load server configurations from YAML file.
        
        Returns number of servers loaded.
        """
        path = config_path or self._config_path
        configs = load_mcp_config(path)
        
        count = 0
        for name, config in configs.items():
            if config.enabled:
                # Validate config
                errors = config.validate()
                if errors:
                    for error in errors:
                        logger.error(error)
                    continue
                
                self.register_server(name, config)
                count += 1
            else:
                logger.debug(f"Skipping disabled server: {name}")
        
        logger.info(f"Loaded {count} MCP server configurations")
        return count
    
    async def connect(self, name: str) -> bool:
        """Connect to a specific server."""
        client = self._clients.get(name)
        if not client:
            logger.error(f"Server '{name}' not registered")
            return False
        
        try:
            await client.connect()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to '{name}': {e}")
            return False
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from a specific server."""
        client = self._clients.get(name)
        if client:
            await client.disconnect()
    
    async def connect_all(self) -> dict[str, bool]:
        """
        Connect to all registered servers.
        
        Returns dict mapping server names to connection success.
        """
        results = {}
        
        # Connect concurrently
        tasks = {
            name: asyncio.create_task(self.connect(name))
            for name in self._clients
        }
        
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Error connecting to '{name}': {e}")
                results[name] = False
        
        connected = sum(1 for v in results.values() if v)
        logger.info(f"Connected to {connected}/{len(results)} MCP servers")
        
        return results
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        tasks = [
            client.disconnect()
            for client in self._clients.values()
            if client.is_connected
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Disconnected from all MCP servers")
    
    async def health_check(self) -> dict[str, bool]:
        """
        Check health of all connected servers.
        
        Returns dict mapping server names to health status.
        """
        results = {}
        
        for name, client in self._clients.items():
            if client.is_connected:
                results[name] = await client.ping()
            else:
                results[name] = False
        
        return results
    
    async def list_all_tools(self) -> dict[str, list[MCPToolSchema]]:
        """
        List tools from all connected servers.
        
        Returns dict mapping server names to their tools.
        """
        results = {}
        
        for name, client in self._clients.items():
            if client.is_connected:
                try:
                    results[name] = await client.list_tools()
                except Exception as e:
                    logger.error(f"Failed to list tools from '{name}': {e}")
                    results[name] = []
        
        return results
    
    async def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: Optional[dict] = None,
    ):
        """
        Call a tool on a specific server.
        
        Args:
            server: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            MCPToolResult from the server
        """
        client = self._clients.get(server)
        if not client:
            raise ValueError(f"Server '{server}' not registered")
        
        if not client.is_connected:
            raise ConnectionError(f"Server '{server}' not connected")
        
        return await client.call_tool(tool_name, arguments)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect_all()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_all()
    
    def __repr__(self) -> str:
        return f"MCPClientManager(servers={self.servers}, connected={self.connected_servers})"
