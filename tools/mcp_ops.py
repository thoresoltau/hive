"""MCP Tool wrappers for Hive Agent Swarm."""

from typing import Optional, Any
import logging

from .base import Tool, ToolParameter, ToolResult, ToolResultStatus
from core.mcp.protocol import MCPToolSchema, MCPToolResult
from core.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPTool(Tool):
    """
    Wrapper that exposes an MCP server tool as a Hive Tool.
    
    Dynamically created based on MCP tool schema from server.
    """
    
    def __init__(
        self,
        mcp_client: MCPClient,
        tool_schema: MCPToolSchema,
        server_name: str,
    ):
        # Don't call super().__init__ with workspace_path
        self._mcp_client = mcp_client
        self._tool_schema = tool_schema
        self._server_name = server_name
        
        # Set tool properties
        self.name = f"mcp_{server_name}_{tool_schema.name}"
        self.description = self._build_description()
        self.parameters = self._convert_parameters()
        
        # Base class attributes
        self.workspace_path = None
    
    def _build_description(self) -> str:
        """Build tool description from MCP schema."""
        desc = self._tool_schema.description or f"MCP tool: {self._tool_schema.name}"
        return f"[MCP:{self._server_name}] {desc}"
    
    def _convert_parameters(self) -> list[ToolParameter]:
        """Convert MCP input schema to Hive ToolParameters."""
        params = []
        
        if not self._tool_schema.input_schema:
            return params
        
        properties = self._tool_schema.input_schema.get("properties", {})
        required = self._tool_schema.input_schema.get("required", [])
        
        for name, prop in properties.items():
            param_type = prop.get("type", "string")
            
            # Map JSON Schema types to our types
            type_mapping = {
                "string": "string",
                "integer": "integer",
                "number": "number",
                "boolean": "boolean",
                "array": "array",
                "object": "object",
            }
            
            params.append(ToolParameter(
                name=name,
                type=type_mapping.get(param_type, "string"),
                description=prop.get("description", ""),
                required=name in required,
                default=prop.get("default"),
            ))
        
        return params
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the MCP tool and return result."""
        if not self._mcp_client.is_connected:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"MCP server '{self._server_name}' not connected",
            )
        
        try:
            # Call the MCP tool
            mcp_result = await self._mcp_client.call_tool(
                self._tool_schema.name,
                kwargs,
            )
            
            # Convert MCP result to Hive ToolResult
            if mcp_result.is_error:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=mcp_result.get_text(),
                )
            
            # Get text content
            text_content = mcp_result.get_text()
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=text_content,
                metadata={
                    "mcp_server": self._server_name,
                    "mcp_tool": self._tool_schema.name,
                    "content_count": len(mcp_result.content),
                },
            )
            
        except Exception as e:
            logger.error(f"MCP tool execution failed: {e}")
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"MCP tool error: {str(e)}",
            )
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type if param.type != "integer" else "number",
                "description": param.description or param.name,
            }
            
            if param.default is not None:
                prop["default"] = param.default
            
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class MCPToolFactory:
    """
    Factory for creating MCPTool instances from MCP servers.
    
    Usage:
        factory = MCPToolFactory(mcp_manager)
        tools = await factory.create_tools_for_server("context7")
        # or
        all_tools = await factory.create_all_tools()
    """
    
    def __init__(self, mcp_manager):
        """
        Initialize factory.
        
        Args:
            mcp_manager: MCPClientManager instance
        """
        from core.mcp.manager import MCPClientManager
        self._manager: MCPClientManager = mcp_manager
    
    async def create_tools_for_server(self, server_name: str) -> list[MCPTool]:
        """
        Create MCPTool instances for all tools from a specific server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of MCPTool instances
        """
        client = self._manager.get_client(server_name)
        if not client:
            logger.warning(f"MCP server '{server_name}' not found")
            return []
        
        if not client.is_connected:
            logger.warning(f"MCP server '{server_name}' not connected")
            return []
        
        try:
            tool_schemas = await client.list_tools()
            tools = []
            
            for schema in tool_schemas:
                tool = MCPTool(
                    mcp_client=client,
                    tool_schema=schema,
                    server_name=server_name,
                )
                tools.append(tool)
                logger.debug(f"Created MCP tool: {tool.name}")
            
            logger.info(f"Created {len(tools)} tools from MCP server '{server_name}'")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to create tools from '{server_name}': {e}")
            return []
    
    async def create_all_tools(self) -> dict[str, list[MCPTool]]:
        """
        Create MCPTool instances for all connected servers.
        
        Returns:
            Dict mapping server names to their tools
        """
        all_tools = {}
        
        for server_name in self._manager.connected_servers:
            tools = await self.create_tools_for_server(server_name)
            if tools:
                all_tools[server_name] = tools
        
        total = sum(len(t) for t in all_tools.values())
        logger.info(f"Created {total} MCP tools from {len(all_tools)} servers")
        
        return all_tools
