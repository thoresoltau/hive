import os
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from core.global_config import GlobalConfigManager, GlobalConfig

class TestGlobalConfig:
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture for GlobalConfigManager with mocked home dir."""
        with patch.object(Path, "home", return_value=tmp_path):
            manager = GlobalConfigManager()
            yield manager

    def test_ensure_config_exists(self, config_manager):
        """Test creation of config directory and file."""
        config_manager.ensure_config_exists()
        
        assert config_manager.config_dir.exists()
        assert config_manager.config_file.exists()
        
        # Check content
        with open(config_manager.config_file) as f:
            data = yaml.safe_load(f)
            assert "openai_api_key" in data
            assert data["model"] == "gpt-4o"

    def test_load_config(self, config_manager):
        """Test loading configuration."""
        config_manager.ensure_config_exists()
        
        # Write custom config
        custom_config = {
            "openai_api_key": "test-key",
            "model": "gpt-4-turbo"
        }
        with open(config_manager.config_file, "w") as f:
            yaml.dump(custom_config, f)
            
        config = config_manager.load()
        assert config.openai_api_key == "test-key"
        assert config.model == "gpt-4-turbo"

    def test_env_var_override(self, config_manager):
        """Test that environment variables override file config."""
        config_manager.ensure_config_exists()
        
        # File config
        with open(config_manager.config_file, "w") as f:
            yaml.dump({"openai_api_key": "file-key"}, f)
            
        # Env var override
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            config = config_manager.load()
            assert config.openai_api_key == "env-key"
            
    def test_get_api_key(self, config_manager):
        """Test get_api_key helper."""
        config_manager.ensure_config_exists()
        
        with open(config_manager.config_file, "w") as f:
            yaml.dump({
                "openai_api_key": "openai-key",
                "tavily_api_key": "tavily-key"
            }, f)
            
        config_manager.load()
        assert config_manager.get_api_key("openai") == "openai-key"
        assert config_manager.get_api_key("tavily") == "tavily-key"
        assert config_manager.get_api_key("unknown") is None
