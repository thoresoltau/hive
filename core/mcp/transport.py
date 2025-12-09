"""MCP Transport implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Any, AsyncIterator
import asyncio
import json
import logging

from .protocol import MCPRequest, MCPResponse, MCPError, MCPErrorCode
from .config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to MCP server."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        pass
    
    @abstractmethod
    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send request and wait for response."""
        pass
    
    async def send_with_retry(self, request: MCPRequest) -> MCPResponse:
        """Send request with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.send(request)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    logger.warning(
                        f"MCP request failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                    )
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise
        
        # Should not reach here, but just in case
        raise last_error or Exception("Unknown error")


class HttpTransport(MCPTransport):
    """HTTP/SSE transport for remote MCP servers."""
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._client: Optional[Any] = None  # httpx.AsyncClient
        self._request_id = 0
    
    async def connect(self) -> None:
        """Create HTTP client."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for HTTP transport. Install with: pip install httpx")
        
        headers = dict(self.config.headers)
        
        # Required headers for MCP
        headers["Content-Type"] = "application/json"
        # Some servers (like Context7) require accepting both JSON and SSE
        headers["Accept"] = "application/json, text/event-stream"
        
        # Add auth header if configured
        auth = self.config.get_auth_header()
        if auth:
            headers[auth[0]] = auth[1]
        
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.request_timeout,
                write=self.config.request_timeout,
                pool=self.config.connect_timeout,
            ),
            headers=headers,
        )
        self._connected = True
        logger.info(f"HTTP transport connected to {self.config.url}")
    
    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.info(f"HTTP transport disconnected from {self.config.url}")
    
    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send HTTP POST request."""
        if not self._client or not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")
        
        try:
            response = await self._client.post(
                self.config.url,
                json=request.model_dump(exclude_none=True),
            )
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            # Handle SSE responses (used by Tavily and others)
            if "text/event-stream" in content_type:
                data = self._parse_sse_response(response.text, request.id)
            else:
                data = response.json()
            
            return MCPResponse(**data)
            
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.INTERNAL_ERROR.value,
                    message=str(e),
                ),
            )
    
    def _parse_sse_response(self, text: str, request_id: str) -> dict:
        """Parse SSE-formatted response text."""
        # SSE format: "event: message\ndata: {...json...}\n\n"
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                json_str = line[5:].strip()
                if json_str:
                    try:
                        data = json.loads(json_str)
                        # Return first valid JSON-RPC response
                        if "jsonrpc" in data:
                            return data
                    except json.JSONDecodeError:
                        continue
        
        # Fallback: return error if no valid response found
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32600, "message": "No valid response in SSE stream"}
        }


class StdioTransport(MCPTransport):
    """Stdio transport for local MCP servers."""
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: dict[str | int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """Start subprocess and connect via stdio."""
        if not self.config.command:
            raise ValueError("No command specified for stdio transport")
        
        cmd = [self.config.command] + self.config.args
        env = {**dict(__import__("os").environ), **self.config.env}
        
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
            env=env,
        )
        
        self._connected = True
        self._reader_task = asyncio.create_task(self._read_responses())
        logger.info(f"Stdio transport started: {' '.join(cmd)}")
    
    async def disconnect(self) -> None:
        """Stop subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
        
        self._connected = False
        self._pending_requests.clear()
        logger.info("Stdio transport stopped")
    
    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send request via stdin and wait for response via stdout."""
        if not self._process or not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")
        
        # Create future for response
        future: asyncio.Future[MCPResponse] = asyncio.Future()
        self._pending_requests[request.id] = future
        
        try:
            # Write request to stdin
            message = request.model_dump_json(exclude_none=True) + "\n"
            self._process.stdin.write(message.encode())
            await self._process.stdin.drain()
            
            # Wait for response with timeout
            response = await asyncio.wait_for(
                future,
                timeout=self.config.request_timeout,
            )
            return response
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request.id, None)
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.REQUEST_TIMEOUT.value,
                    message=f"Request timed out after {self.config.request_timeout}s",
                ),
            )
        except Exception as e:
            self._pending_requests.pop(request.id, None)
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.INTERNAL_ERROR.value,
                    message=str(e),
                ),
            )
    
    async def _read_responses(self) -> None:
        """Background task to read responses from stdout."""
        while self._connected and self._process:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                data = json.loads(line.decode())
                response = MCPResponse(**data)
                
                # Find and complete the pending request
                future = self._pending_requests.pop(response.id, None)
                if future and not future.done():
                    future.set_result(response)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from MCP server: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading MCP response: {e}")


class SSETransport(MCPTransport):
    """
    Server-Sent Events transport for MCP servers.
    
    Used by servers like Context7 that use SSE for streaming responses.
    Sends requests via POST and receives responses via SSE stream.
    """
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._client: Optional[Any] = None  # httpx.AsyncClient
        self._request_counter = 0
    
    async def connect(self) -> None:
        """Create HTTP client for SSE."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for SSE transport. Install with: pip install httpx")
        
        headers = dict(self.config.headers)
        # Tavily and other MCP servers require accepting both JSON and SSE
        headers["Accept"] = "application/json, text/event-stream"
        headers["Content-Type"] = "application/json"
        
        # Add auth header if configured
        auth = self.config.get_auth_header()
        if auth:
            headers[auth[0]] = auth[1]
        
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.request_timeout,
                write=self.config.request_timeout,
                pool=self.config.connect_timeout,
            ),
            headers=headers,
        )
        self._connected = True
        logger.info(f"SSE transport connected to {self.config.url}")
    
    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.info(f"SSE transport disconnected from {self.config.url}")
    
    async def send(self, request: MCPRequest) -> MCPResponse:
        """Send request and receive SSE response."""
        if not self._client or not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")
        
        try:
            from httpx_sse import aconnect_sse
            
            request_data = request.model_dump(exclude_none=True)
            
            async with aconnect_sse(
                self._client,
                "POST",
                self.config.url,
                json=request_data,
            ) as event_source:
                # Collect all SSE events
                result_data = None
                
                async for event in event_source.aiter_sse():
                    if event.event == "message" or event.event is None:
                        try:
                            data = json.loads(event.data)
                            
                            # Check if this is a JSON-RPC response
                            if "jsonrpc" in data and data.get("id") == request.id:
                                result_data = data
                                break
                            
                            # Some servers send the result directly
                            if "result" in data or "error" in data:
                                result_data = {
                                    "jsonrpc": "2.0",
                                    "id": request.id,
                                    **data
                                }
                                break
                                
                        except json.JSONDecodeError:
                            logger.debug(f"Non-JSON SSE event: {event.data[:100]}")
                            continue
                    
                    elif event.event == "error":
                        return MCPResponse(
                            id=request.id,
                            error=MCPError(
                                code=MCPErrorCode.INTERNAL_ERROR.value,
                                message=event.data,
                            ),
                        )
                
                if result_data:
                    return MCPResponse(**result_data)
                
                # No response received
                return MCPResponse(
                    id=request.id,
                    error=MCPError(
                        code=MCPErrorCode.INTERNAL_ERROR.value,
                        message="No response received from SSE stream",
                    ),
                )
                
        except Exception as e:
            logger.error(f"SSE request failed: {e}")
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.INTERNAL_ERROR.value,
                    message=str(e),
                ),
            )


def create_transport(config: MCPServerConfig) -> MCPTransport:
    """Factory function to create appropriate transport."""
    if config.transport == "stdio":
        return StdioTransport(config)
    elif config.transport == "http":
        return HttpTransport(config)
    elif config.transport == "sse":
        return SSETransport(config)
    else:
        raise ValueError(f"Unknown transport type: {config.transport}")
