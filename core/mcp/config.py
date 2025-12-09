"""MCP Server configuration."""

from typing import Optional, Literal
from dataclasses import dataclass, field
from pathlib import Path
import os
import yaml


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    
    name: str
    transport: Literal["stdio", "http", "sse"]
    enabled: bool = True
    description: Optional[str] = None
    
    # For stdio transport
    command: Optional[str] = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    
    # For http/sse transport
    url: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    
    # Authentication
    api_key: Optional[str] = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "
    
    # Timeouts (seconds)
    connect_timeout: int = 30
    request_timeout: int = 120
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    def __post_init__(self):
        """Resolve environment variables in config values."""
        self.url = self._resolve_env(self.url)
        self.api_key = self._resolve_env(self.api_key)
        self.command = self._resolve_env(self.command)
        self.cwd = self._resolve_env(self.cwd)
        
        # Resolve env vars in headers
        self.headers = {
            k: self._resolve_env(v) for k, v in self.headers.items()
        }
        
        # Resolve env vars in env dict
        self.env = {
            k: self._resolve_env(v) for k, v in self.env.items()
        }
    
    def _resolve_env(self, value: Optional[str]) -> Optional[str]:
        """Resolve ${VAR} patterns in config values."""
        if not value:
            return value
        
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, "")
        
        # Replace all ${VAR} patterns
        return re.sub(r'\$\{([^}]+)\}', replace_var, value)
    
    def get_auth_header(self) -> Optional[tuple[str, str]]:
        """Get authentication header if api_key is set."""
        if not self.api_key:
            return None
        return (self.api_key_header, f"{self.api_key_prefix}{self.api_key}")
    
    def validate(self) -> list[str]:
        """Validate configuration. Returns list of error messages."""
        errors = []
        
        if self.transport == "stdio":
            if not self.command:
                errors.append(f"Server '{self.name}': stdio transport requires 'command'")
        elif self.transport in ("http", "sse"):
            if not self.url:
                errors.append(f"Server '{self.name}': {self.transport} transport requires 'url'")
        
        return errors


def load_mcp_config(config_path: Optional[Path] = None) -> dict[str, MCPServerConfig]:
    """
    Load MCP server configurations from YAML file.
    
    Args:
        config_path: Path to config file. Defaults to config/mcp_servers.yaml
        
    Returns:
        Dict mapping server names to MCPServerConfig objects
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "mcp_servers.yaml"
    
    if not config_path.exists():
        return {}
    
    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}
    
    servers = {}
    mcp_servers = data.get("mcp_servers", {})
    
    for name, config in mcp_servers.items():
        if config is None:
            continue
            
        servers[name] = MCPServerConfig(
            name=name,
            transport=config.get("transport", "http"),
            enabled=config.get("enabled", True),
            description=config.get("description"),
            command=config.get("command"),
            args=config.get("args", []),
            env=config.get("env", {}),
            cwd=config.get("cwd"),
            url=config.get("url"),
            headers=config.get("headers", {}),
            api_key=config.get("api_key"),
            api_key_header=config.get("api_key_header", "Authorization"),
            api_key_prefix=config.get("api_key_prefix", "Bearer "),
            connect_timeout=config.get("connect_timeout", 30),
            request_timeout=config.get("request_timeout", 120),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
        )
    
    return servers
