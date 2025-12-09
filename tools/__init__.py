"""Tools module for Hive Agent Swarm."""

from .base import Tool, ToolResult, ToolRegistry
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
from .mcp_ops import MCPTool, MCPToolFactory
from .rag import (
    RAGSearchTool,
    EmbeddingService,
    CodeChunker,
    VectorDB,
    CodebaseIndexer,
)

__all__ = [
    # Base
    "Tool",
    "ToolResult",
    "ToolRegistry",
    # File ops
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirectoryTool",
    "FindFilesTool",
    "DeleteFileTool",
    "MoveFileTool",
    "AppendFileTool",
    "CreateDirectoryTool",
    # Git ops
    "GitStatusTool",
    "GitBranchTool",
    "GitCommitTool",
    "GitDiffTool",
    "GitLogTool",
    "GitCurrentBranchTool",
    "GitPushTool",
    "GitPullTool",
    "GitResetTool",
    "GitCheckoutFileTool",
    # Shell ops
    "RunCommandTool",
    # MCP ops
    "MCPTool",
    "MCPToolFactory",
    # RAG ops
    "RAGSearchTool",
    "EmbeddingService",
    "CodeChunker",
    "VectorDB",
    "CodebaseIndexer",
]
