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
    model_name: str = "gpt-4o"
    model_name_fast: str = "gpt-4o-mini"
    
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
                "model_name": "gpt-4o",
                "model_name_fast": "gpt-4o-mini"
            }
            with open(self.config_file, "w") as f:
                yaml.dump(default_config, f)
    
    def load(self) -> GlobalConfig:
        """Load global configuration."""
        self.ensure_config_exists()
        
        with open(self.config_file, "r") as f:
            data = yaml.safe_load(f) or {}
            
        # Helper to check multiple keys in data
        def get_from_data(keys: list[str]) -> Optional[Any]:
            for key in keys:
                if key in data and data[key]:
                    return data[key]
            return None

        # Environment variables override config file
        # Mapping: Env Var -> Config Field
        env_map = {
            "OPENAI_API_KEY": "openai_api_key",
            "TAVILY_API_KEY": "tavily_api_key",
            "MODEL_NAME": "model_name",
            "MODEL_NAME_FAST": "model_name_fast",
            "MODEL_FAST": "model_name_fast", # Alias
        }

        # Apply env overrides
        for env_var, field in env_map.items():
            if os.getenv(env_var):
                data[field] = os.getenv(env_var)
        
        # Normalize keys in data (allow OPENAI_API_KEY in yaml)
        normalized_data = {}
        # fields we care about
        fields_map = {
            "openai_api_key": ["openai_api_key", "OPENAI_API_KEY", "openai_key"],
            "tavily_api_key": ["tavily_api_key", "TAVILY_API_KEY", "tavily_key"],
            "model_name": ["model_name", "MODEL_NAME", "model"], # Support old 'model' key too
            "model_name_fast": ["model_name_fast", "MODEL_NAME_FAST", "model_fast", "MODEL_FAST"],
            "mcp_registry_url": ["mcp_registry_url"]
        }
        
        for field, variants in fields_map.items():
            # First checking data with variants
            val = get_from_data(variants)
            if val:
                normalized_data[field] = val
            # Keep existing default if not found (will be set by Pydantic default)
            
        self.config = GlobalConfig(**normalized_data)
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
