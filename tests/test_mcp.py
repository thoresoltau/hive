"""Tests for MCP (Model Context Protocol) implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from core.mcp.protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPToolSchema,
    MCPToolResult,
    MCPResource,
    MCPResourceContent,
    MCPInitializeResult,
    MCPServerCapabilities,
    MCPServerInfo,
)
from core.mcp.config import MCPServerConfig, load_mcp_config
from core.mcp.client import MCPClient
from core.mcp.manager import MCPClientManager
from tools.mcp_ops import MCPTool, MCPToolFactory
from tools.base import ToolRegistry, ToolResultStatus


class TestMCPProtocol:
    """Tests for MCP protocol types."""

    def test_mcp_request(self):
        """Should create valid MCP request."""
        request = MCPRequest(
            id="test-1",
            method="tools/list",
            params={"cursor": None},
        )
        
        assert request.jsonrpc == "2.0"
        assert request.id == "test-1"
        assert request.method == "tools/list"
        assert request.params == {"cursor": None}

    def test_mcp_response_success(self):
        """Should create successful MCP response."""
        response = MCPResponse(
            id="test-1",
            result={"tools": []},
        )
        
        assert not response.is_error
        assert response.result == {"tools": []}
        assert response.error is None

    def test_mcp_response_error(self):
        """Should create error MCP response."""
        response = MCPResponse(
            id="test-1",
            error=MCPError(code=-32600, message="Invalid request"),
        )
        
        assert response.is_error
        assert response.error.code == -32600
        assert response.error.message == "Invalid request"

    def test_mcp_tool_schema(self):
        """Should parse tool schema with input parameters."""
        schema = MCPToolSchema(
            name="get_docs",
            description="Get documentation for a library",
            inputSchema={
                "type": "object",
                "properties": {
                    "library": {"type": "string", "description": "Library name"},
                    "topic": {"type": "string", "description": "Topic to search"},
                },
                "required": ["library"],
            },
        )
        
        assert schema.name == "get_docs"
        params = schema.get_parameters()
        assert len(params) == 2
        assert params[0].name == "library"
        assert params[0].required == True
        assert params[1].name == "topic"
        assert params[1].required == False

    def test_mcp_tool_result(self):
        """Should parse tool result with text content."""
        result = MCPToolResult(
            content=[
                {"type": "text", "text": "# React Hooks\n\nHooks are..."},
                {"type": "text", "text": "## useState\n\nuseState is..."},
            ],
            isError=False,
        )
        
        assert not result.is_error
        assert len(result.content) == 2
        text = result.get_text()
        assert "React Hooks" in text
        assert "useState" in text


class TestMCPConfig:
    """Tests for MCP server configuration."""

    def test_config_creation(self):
        """Should create config with defaults."""
        config = MCPServerConfig(
            name="test",
            transport="http",
            url="https://example.com/mcp",
        )
        
        assert config.name == "test"
        assert config.transport == "http"
        assert config.enabled == True
        assert config.connect_timeout == 30
        assert config.request_timeout == 120

    def test_config_env_resolution(self, monkeypatch):
        """Should resolve environment variables."""
        monkeypatch.setenv("TEST_API_KEY", "secret123")
        
        config = MCPServerConfig(
            name="test",
            transport="http",
            url="https://example.com/mcp",
            api_key="${TEST_API_KEY}",
        )
        
        assert config.api_key == "secret123"

    def test_config_auth_header(self):
        """Should generate auth header."""
        config = MCPServerConfig(
            name="test",
            transport="http",
            url="https://example.com/mcp",
            api_key="my-api-key",
        )
        
        header = config.get_auth_header()
        assert header == ("Authorization", "Bearer my-api-key")

    def test_config_validation_http(self):
        """Should validate HTTP config requires URL."""
        config = MCPServerConfig(
            name="test",
            transport="http",
        )
        
        errors = config.validate()
        assert len(errors) == 1
        assert "url" in errors[0].lower()

    def test_config_validation_stdio(self):
        """Should validate stdio config requires command."""
        config = MCPServerConfig(
            name="test",
            transport="stdio",
        )
        
        errors = config.validate()
        assert len(errors) == 1
        assert "command" in errors[0].lower()

    def test_load_config_file(self, tmp_path):
        """Should load config from YAML file."""
        config_file = tmp_path / "mcp_servers.yaml"
        config_file.write_text("""
mcp_servers:
  test_server:
    transport: http
    url: https://test.com/mcp
    enabled: true
  disabled_server:
    transport: http
    url: https://disabled.com/mcp
    enabled: false
""")
        
        configs = load_mcp_config(config_file)
        
        assert "test_server" in configs
        assert "disabled_server" in configs
        assert configs["test_server"].url == "https://test.com/mcp"
        assert configs["test_server"].enabled == True
        assert configs["disabled_server"].enabled == False


class TestMCPClient:
    """Tests for MCP client."""

    @pytest.fixture
    def mock_transport(self):
        """Create mock transport."""
        transport = AsyncMock()
        transport.is_connected = True
        return transport

    @pytest.fixture
    def client_config(self):
        """Create test client config."""
        return MCPServerConfig(
            name="test",
            transport="http",
            url="https://test.com/mcp",
        )

    async def test_client_connect(self, client_config):
        """Should connect and initialize."""
        client = MCPClient(client_config)
        
        with patch("core.mcp.client.create_transport") as mock_create:
            mock_transport = AsyncMock()
            mock_transport.is_connected = True
            mock_transport.send_with_retry = AsyncMock(return_value=MCPResponse(
                id="test-1",
                result={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "test-server", "version": "1.0"},
                },
            ))
            mock_create.return_value = mock_transport
            
            await client.connect()
            
            assert client.is_connected
            assert client.is_initialized
            assert client.capabilities.supports_tools

    async def test_client_list_tools(self, client_config):
        """Should list tools from server."""
        client = MCPClient(client_config)
        client._initialized = True
        client._capabilities = MCPServerCapabilities(tools={})
        
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_transport.send_with_retry = AsyncMock(return_value=MCPResponse(
            id="test-2",
            result={
                "tools": [
                    {"name": "get_docs", "description": "Get documentation"},
                    {"name": "search", "description": "Search content"},
                ]
            },
        ))
        client._transport = mock_transport
        
        tools = await client.list_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "get_docs"
        assert tools[1].name == "search"

    async def test_client_call_tool(self, client_config):
        """Should call tool and return result."""
        client = MCPClient(client_config)
        client._initialized = True
        
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_transport.send_with_retry = AsyncMock(return_value=MCPResponse(
            id="test-3",
            result={
                "content": [{"type": "text", "text": "Documentation content..."}],
                "isError": False,
            },
        ))
        client._transport = mock_transport
        
        result = await client.call_tool("get_docs", {"library": "react"})
        
        assert not result.is_error
        assert "Documentation content" in result.get_text()


class TestMCPClientManager:
    """Tests for MCP client manager."""

    def test_register_server(self):
        """Should register server."""
        manager = MCPClientManager()
        config = MCPServerConfig(name="test", transport="http", url="https://test.com")
        
        manager.register_server("test", config)
        
        assert "test" in manager.servers
        assert manager.get_client("test") is not None

    def test_unregister_server(self):
        """Should unregister server."""
        manager = MCPClientManager()
        config = MCPServerConfig(name="test", transport="http", url="https://test.com")
        
        manager.register_server("test", config)
        manager.unregister_server("test")
        
        assert "test" not in manager.servers

    async def test_connect_all(self):
        """Should connect to all servers."""
        manager = MCPClientManager()
        
        # Register mock clients
        mock_client1 = AsyncMock(spec=MCPClient)
        mock_client1.is_connected = True
        mock_client1.connect = AsyncMock()
        
        mock_client2 = AsyncMock(spec=MCPClient)
        mock_client2.is_connected = True
        mock_client2.connect = AsyncMock()
        
        manager._clients = {"server1": mock_client1, "server2": mock_client2}
        
        with patch.object(manager, "connect", side_effect=[True, True]) as mock_connect:
            results = await manager.connect_all()
        
        assert results["server1"] == True
        assert results["server2"] == True

    def test_load_from_config(self, tmp_path):
        """Should load servers from config file."""
        config_file = tmp_path / "mcp_servers.yaml"
        config_file.write_text("""
mcp_servers:
  server1:
    transport: http
    url: https://server1.com/mcp
    enabled: true
  server2:
    transport: http
    url: https://server2.com/mcp
    enabled: false
""")
        
        manager = MCPClientManager(config_path=config_file)
        count = manager.load_from_config()
        
        # Only enabled servers should be loaded
        assert count == 1
        assert "server1" in manager.servers
        assert "server2" not in manager.servers


class TestMCPTool:
    """Tests for MCPTool wrapper."""

    @pytest.fixture
    def mock_client(self):
        """Create mock MCP client."""
        client = AsyncMock(spec=MCPClient)
        client.is_connected = True
        return client

    @pytest.fixture
    def tool_schema(self):
        """Create test tool schema."""
        return MCPToolSchema(
            name="get_docs",
            description="Get documentation for a library",
            inputSchema={
                "type": "object",
                "properties": {
                    "library": {"type": "string", "description": "Library name"},
                    "topic": {"type": "string", "description": "Topic to search"},
                },
                "required": ["library"],
            },
        )

    def test_mcp_tool_creation(self, mock_client, tool_schema):
        """Should create MCPTool from schema."""
        tool = MCPTool(
            mcp_client=mock_client,
            tool_schema=tool_schema,
            server_name="context7",
        )
        
        assert tool.name == "mcp_context7_get_docs"
        assert "context7" in tool.description
        assert len(tool.parameters) == 2
        
        # Check parameter conversion
        lib_param = next(p for p in tool.parameters if p.name == "library")
        assert lib_param.required == True
        
        topic_param = next(p for p in tool.parameters if p.name == "topic")
        assert topic_param.required == False

    async def test_mcp_tool_execute_success(self, mock_client, tool_schema):
        """Should execute MCP tool and return result."""
        mock_client.call_tool = AsyncMock(return_value=MCPToolResult(
            content=[{"type": "text", "text": "# React Hooks\n\nDocumentation..."}],
            isError=False,
        ))
        
        tool = MCPTool(mock_client, tool_schema, "context7")
        result = await tool.execute(library="react", topic="hooks")
        
        assert result.success
        assert "React Hooks" in result.output
        assert result.metadata["mcp_server"] == "context7"

    async def test_mcp_tool_execute_error(self, mock_client, tool_schema):
        """Should handle MCP tool error."""
        mock_client.call_tool = AsyncMock(return_value=MCPToolResult(
            content=[{"type": "text", "text": "Library not found"}],
            isError=True,
        ))
        
        tool = MCPTool(mock_client, tool_schema, "context7")
        result = await tool.execute(library="unknown")
        
        assert result.status == ToolResultStatus.ERROR

    async def test_mcp_tool_not_connected(self, mock_client, tool_schema):
        """Should return error if client not connected."""
        mock_client.is_connected = False
        
        tool = MCPTool(mock_client, tool_schema, "context7")
        result = await tool.execute(library="react")
        
        assert result.status == ToolResultStatus.ERROR
        assert "not connected" in result.error.lower()

    def test_mcp_tool_openai_schema(self, mock_client, tool_schema):
        """Should convert to OpenAI function schema."""
        tool = MCPTool(mock_client, tool_schema, "context7")
        schema = tool.to_openai_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "mcp_context7_get_docs"
        assert "library" in schema["function"]["parameters"]["properties"]
        assert "library" in schema["function"]["parameters"]["required"]


class TestMCPToolFactory:
    """Tests for MCPToolFactory."""

    async def test_create_tools_for_server(self):
        """Should create tools from server."""
        mock_manager = MagicMock()
        mock_client = AsyncMock(spec=MCPClient)
        mock_client.is_connected = True
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolSchema(name="tool1", description="Tool 1"),
            MCPToolSchema(name="tool2", description="Tool 2"),
        ])
        mock_manager.get_client.return_value = mock_client
        
        factory = MCPToolFactory(mock_manager)
        tools = await factory.create_tools_for_server("test_server")
        
        assert len(tools) == 2
        assert tools[0].name == "mcp_test_server_tool1"
        assert tools[1].name == "mcp_test_server_tool2"

    async def test_create_tools_server_not_found(self):
        """Should return empty list if server not found."""
        mock_manager = MagicMock()
        mock_manager.get_client.return_value = None
        
        factory = MCPToolFactory(mock_manager)
        tools = await factory.create_tools_for_server("unknown")
        
        assert tools == []


class TestToolRegistryMCP:
    """Tests for ToolRegistry MCP integration."""

    async def test_register_mcp_tools(self):
        """Should register MCP tools in registry."""
        registry = ToolRegistry()
        
        mock_manager = MagicMock()
        mock_manager.connected_servers = ["server1"]
        mock_client = AsyncMock(spec=MCPClient)
        mock_client.is_connected = True
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolSchema(name="tool1", description="Tool 1"),
        ])
        mock_manager.get_client.return_value = mock_client
        
        count = await registry.register_mcp_tools(mock_manager)
        
        assert count == 1
        assert registry.get("mcp_server1_tool1") is not None

    def test_get_mcp_tools(self):
        """Should filter MCP tools from registry."""
        registry = ToolRegistry()
        
        # Add a regular tool
        from tools.file_ops import ReadFileTool
        registry.register(ReadFileTool())
        
        # Add mock MCP tool
        mock_client = AsyncMock(spec=MCPClient)
        mock_client.is_connected = True
        schema = MCPToolSchema(name="test", description="Test")
        mcp_tool = MCPTool(mock_client, schema, "server1")
        registry.register(mcp_tool)
        
        mcp_tools = registry.get_mcp_tools()
        
        assert len(mcp_tools) == 1
        assert mcp_tools[0].name == "mcp_server1_test"

    def test_unregister_tool(self):
        """Should unregister tool by name."""
        registry = ToolRegistry()
        
        from tools.file_ops import ReadFileTool
        registry.register(ReadFileTool())
        
        assert registry.get("read_file") is not None
        
        result = registry.unregister("read_file")
        
        assert result == True
        assert registry.get("read_file") is None
