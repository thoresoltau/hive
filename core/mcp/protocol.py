"""MCP Protocol types based on JSON-RPC 2.0."""

from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# JSON-RPC 2.0 Base Types
# =============================================================================

class MCPRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: Optional[dict[str, Any]] = None


class MCPError(BaseModel):
    """JSON-RPC 2.0 error."""
    
    code: int
    message: str
    data: Optional[Any] = None


class MCPResponse(BaseModel):
    """JSON-RPC 2.0 response."""
    
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: Optional[Any] = None
    error: Optional[MCPError] = None
    
    @property
    def is_error(self) -> bool:
        return self.error is not None


# =============================================================================
# MCP Tool Types
# =============================================================================

class MCPToolParameter(BaseModel):
    """Parameter definition for an MCP tool."""
    
    name: str
    type: str
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[list[Any]] = None


class MCPToolSchema(BaseModel):
    """Schema for an MCP tool (from tools/list)."""
    
    name: str
    description: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = Field(default=None, alias="inputSchema")
    
    class Config:
        populate_by_name = True
    
    def get_parameters(self) -> list[MCPToolParameter]:
        """Extract parameters from JSON Schema input_schema."""
        if not self.input_schema:
            return []
        
        properties = self.input_schema.get("properties", {})
        required = self.input_schema.get("required", [])
        
        params = []
        for name, prop in properties.items():
            params.append(MCPToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description"),
                required=name in required,
                default=prop.get("default"),
                enum=prop.get("enum"),
            ))
        return params


class MCPToolResultContent(BaseModel):
    """Content item in tool result."""
    
    type: Literal["text", "image", "resource"] = "text"
    text: Optional[str] = None
    data: Optional[str] = None  # Base64 for images
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    
    class Config:
        populate_by_name = True


class MCPToolResult(BaseModel):
    """Result from calling an MCP tool."""
    
    content: list[MCPToolResultContent] = Field(default_factory=list)
    is_error: bool = Field(default=False, alias="isError")
    
    class Config:
        populate_by_name = True
    
    def get_text(self) -> str:
        """Get combined text content."""
        texts = [c.text for c in self.content if c.type == "text" and c.text]
        return "\n".join(texts)


# =============================================================================
# MCP Resource Types
# =============================================================================

class MCPResource(BaseModel):
    """Resource definition (from resources/list)."""
    
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    
    class Config:
        populate_by_name = True


class MCPResourceContent(BaseModel):
    """Content of a resource (from resources/read)."""
    
    uri: str
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    text: Optional[str] = None
    blob: Optional[str] = None  # Base64 encoded
    
    class Config:
        populate_by_name = True


# =============================================================================
# MCP Capability Types
# =============================================================================

class MCPServerCapabilities(BaseModel):
    """Server capabilities from initialize response."""
    
    tools: Optional[dict[str, Any]] = None
    resources: Optional[dict[str, Any]] = None
    prompts: Optional[dict[str, Any]] = None
    logging: Optional[dict[str, Any]] = None
    
    @property
    def supports_tools(self) -> bool:
        return self.tools is not None
    
    @property
    def supports_resources(self) -> bool:
        return self.resources is not None


class MCPServerInfo(BaseModel):
    """Server info from initialize response."""
    
    name: str
    version: str


class MCPInitializeResult(BaseModel):
    """Result from initialize request."""
    
    protocol_version: str = Field(alias="protocolVersion")
    capabilities: MCPServerCapabilities
    server_info: MCPServerInfo = Field(alias="serverInfo")
    
    class Config:
        populate_by_name = True


# =============================================================================
# Standard MCP Error Codes
# =============================================================================

class MCPErrorCode(Enum):
    """Standard MCP error codes."""
    
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP specific errors
    CONNECTION_CLOSED = -32000
    REQUEST_TIMEOUT = -32001
