"""Global configuration management for Hive."""

import os
import yaml
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field


class GlobalConfig(BaseModel):
    """Global configuration model."""
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    model: str = "gpt-4o"
    model_fast: str = "gpt-4o-mini"
    
    # Optional: Custom MCP server registry URL
    mcp_registry_url: Optional[str] = None


class GlobalConfigManager:
    """Manages the global configuration in ~/.hive/config.yaml."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".hive"
        self.config_file = self.config_dir / "config.yaml"
        self.config: Optional[GlobalConfig] = None
        
    def ensure_config_exists(self) -> None:
        """Create ~/.hive directory and default config if not exists."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)
            
        if not self.config_file.exists():
            default_config = {
                "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
                "tavily_api_key": os.getenv("TAVILY_API_KEY", ""),
                "model": "gpt-4o",
                "model_fast": "gpt-4o-mini"
            }
            with open(self.config_file, "w") as f:
                yaml.dump(default_config, f)
    
    def load(self) -> GlobalConfig:
        """Load global configuration."""
        self.ensure_config_exists()
        
        with open(self.config_file, "r") as f:
            data = yaml.safe_load(f) or {}
            
        # Environment variables override config file
        if os.getenv("OPENAI_API_KEY"):
            data["openai_api_key"] = os.getenv("OPENAI_API_KEY")
            
        if os.getenv("TAVILY_API_KEY"):
            data["tavily_api_key"] = os.getenv("TAVILY_API_KEY")
            
        self.config = GlobalConfig(**data)
        return self.config
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for service (openai, tavily)."""
        if not self.config:
            self.load()
            
        if service == "openai":
            return self.config.openai_api_key
        elif service == "tavily":
            return self.config.tavily_api_key
        return None
