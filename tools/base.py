"""Base classes for tools that agents can use."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Type
from enum import Enum


class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    status: ToolResultStatus
    output: Any
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ToolResultStatus.SUCCESS

    def to_context(self) -> str:
        """Format result for LLM context."""
        if self.status == ToolResultStatus.ERROR:
            return f"❌ Fehler: {self.error}"
        return str(self.output)


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    items_type: Optional[str] = None  # For array types: type of items (e.g., "string")


class Tool(ABC):
    """
    Abstract base class for all tools.
    
    Tools provide concrete capabilities to agents:
    - File operations (read, write, edit)
    - Git operations
    - Code analysis
    - External API calls
    """
    
    name: str = "base_tool"
    description: str = "Base tool"
    parameters: list[ToolParameter] = []

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_schema(self) -> dict:
        """Get OpenAI function schema for this tool."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop_schema = {
                "type": param.type,
                "description": param.description,
            }
            # Add items schema for array types
            if param.type == "array":
                prop_schema["items"] = {"type": param.items_type or "string"}
            
            properties[param.name] = prop_schema
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

    def validate_params(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate parameters before execution."""
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"
        return True, None


class ToolRegistry:
    """Registry for available tools."""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        """Get OpenAI function schemas for all tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def register_defaults(self, workspace_path: Optional[str] = None) -> None:
        """Register default file and git operation tools."""
        from .file_ops import (
            ReadFileTool,
            WriteFileTool,
            EditFileTool,
            ListDirectoryTool,
            FindFilesTool,
            DeleteFileTool,
            MoveFileTool,
            AppendFileTool,
            CreateDirectoryTool,
        )
        from .git_ops import (
            GitStatusTool,
            GitBranchTool,
            GitCommitTool,
            GitDiffTool,
            GitLogTool,
            GitCurrentBranchTool,
            GitPushTool,
            GitPullTool,
            GitResetTool,
            GitCheckoutFileTool,
        )
        from .shell_ops import RunCommandTool
        
        # File tools
        self.register(ReadFileTool(workspace_path))
        self.register(WriteFileTool(workspace_path))
        self.register(EditFileTool(workspace_path))
        self.register(ListDirectoryTool(workspace_path))
        self.register(FindFilesTool(workspace_path))
        self.register(DeleteFileTool(workspace_path))
        self.register(MoveFileTool(workspace_path))
        self.register(AppendFileTool(workspace_path))
        self.register(CreateDirectoryTool(workspace_path))
        
        # Git tools
        self.register(GitStatusTool(workspace_path))
        self.register(GitBranchTool(workspace_path))
        self.register(GitCommitTool(workspace_path))
        self.register(GitDiffTool(workspace_path))
        self.register(GitLogTool(workspace_path))
        self.register(GitCurrentBranchTool(workspace_path))
        self.register(GitPushTool(workspace_path))
        self.register(GitPullTool(workspace_path))
        self.register(GitResetTool(workspace_path))
        self.register(GitCheckoutFileTool(workspace_path))
        
        # Shell tools
        self.register(RunCommandTool(workspace_path))
    
    def register_rag_tool(self, workspace_path: Optional[str] = None) -> bool:
        """
        Register RAG search tool (optional, requires indexed codebase).
        
        Args:
            workspace_path: Path to workspace with .hive/vectordb
            
        Returns:
            True if registration successful
        """
        try:
            from .rag import RAGSearchTool
            self.register(RAGSearchTool(workspace_path))
            return True
        except ImportError as e:
            print(f"RAG tool not available: {e}")
            return False

    async def register_mcp_tools(self, mcp_manager) -> int:
        """
        Register tools from connected MCP servers.
        
        Args:
            mcp_manager: MCPClientManager instance
            
        Returns:
            Number of MCP tools registered
        """
        from .mcp_ops import MCPToolFactory
        
        factory = MCPToolFactory(mcp_manager)
        all_tools = await factory.create_all_tools()
        
        count = 0
        for server_name, tools in all_tools.items():
            for tool in tools:
                self.register(tool)
                count += 1
        
        return count
    
    def get_mcp_tools(self) -> list:
        """Get all registered MCP tools."""
        from .mcp_ops import MCPTool
        return [t for t in self._tools.values() if isinstance(t, MCPTool)]
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
