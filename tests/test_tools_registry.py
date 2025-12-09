"""Tests for tool registry and base classes."""

import pytest

from tools.base import (
    Tool,
    ToolResult,
    ToolResultStatus,
    ToolParameter,
    ToolRegistry,
)


class MockTool(Tool):
    """Mock tool for testing."""
    
    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = [
        ToolParameter(
            name="required_param",
            type="string",
            description="A required parameter",
            required=True,
        ),
        ToolParameter(
            name="optional_param",
            type="string",
            description="An optional parameter",
            required=False,
        ),
    ]
    
    async def execute(self, required_param: str, optional_param: str = None) -> ToolResult:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"param": required_param, "optional": optional_param},
        )


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_property(self):
        """Should return True for success status."""
        result = ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"data": "test"},
        )
        
        assert result.success == True

    def test_success_property_false(self):
        """Should return False for error status."""
        result = ToolResult(
            status=ToolResultStatus.ERROR,
            output=None,
            error="Something went wrong",
        )
        
        assert result.success == False

    def test_to_context_success(self):
        """Should format success result."""
        result = ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"key": "value"},
        )
        
        context = result.to_context()
        
        assert "key" in context
        assert "value" in context

    def test_to_context_error(self):
        """Should format error result."""
        result = ToolResult(
            status=ToolResultStatus.ERROR,
            output=None,
            error="Error message",
        )
        
        context = result.to_context()
        
        assert "❌" in context
        assert "Error message" in context


class TestTool:
    """Tests for Tool base class."""

    def test_get_schema(self):
        """Should generate OpenAI function schema."""
        tool = MockTool()
        schema = tool.get_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "mock_tool"
        assert "parameters" in schema["function"]
        assert "required_param" in schema["function"]["parameters"]["properties"]

    def test_schema_required_fields(self):
        """Should mark required fields correctly."""
        tool = MockTool()
        schema = tool.get_schema()
        
        required = schema["function"]["parameters"]["required"]
        assert "required_param" in required
        assert "optional_param" not in required

    def test_validate_params_success(self):
        """Should validate required params."""
        tool = MockTool()
        valid, error = tool.validate_params(required_param="test")
        
        assert valid == True
        assert error is None

    def test_validate_params_missing(self):
        """Should fail for missing required params."""
        tool = MockTool()
        valid, error = tool.validate_params()
        
        assert valid == False
        assert "required_param" in error

    async def test_execute(self):
        """Should execute tool."""
        tool = MockTool()
        result = await tool.execute(required_param="test")
        
        assert result.success
        assert result.output["param"] == "test"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self):
        """Should register a tool."""
        registry = ToolRegistry()
        tool = MockTool()
        
        registry.register(tool)
        
        assert registry.get("mock_tool") is tool

    def test_get_nonexistent_tool(self):
        """Should return None for non-existent tool."""
        registry = ToolRegistry()
        
        assert registry.get("nonexistent") is None

    def test_get_all_tools(self):
        """Should return all registered tools."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool1.name = "tool1"
        tool2 = MockTool()
        tool2.name = "tool2"
        
        registry.register(tool1)
        registry.register(tool2)
        
        all_tools = registry.get_all()
        
        assert len(all_tools) == 2

    def test_get_schemas(self):
        """Should return schemas for all tools."""
        registry = ToolRegistry()
        registry.register(MockTool())
        
        schemas = registry.get_schemas()
        
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "mock_tool"

    def test_register_defaults(self, temp_dir):
        """Should register default tools."""
        registry = ToolRegistry()
        registry.register_defaults(workspace_path=str(temp_dir))
        
        all_tools = registry.get_all()
        
        # Should have file tools + git tools
        assert len(all_tools) >= 10
        
        # Check some expected tools
        assert registry.get("read_file") is not None
        assert registry.get("write_file") is not None
        assert registry.get("git_status") is not None
        assert registry.get("git_commit") is not None
