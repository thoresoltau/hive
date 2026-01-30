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
            assert data["model_name"] == "gpt-4o"

    def test_load_config(self, config_manager):
        """Test loading configuration."""
        config_manager.ensure_config_exists()
        
        # Write custom config
        custom_config = {
            "openai_api_key": "test-key",
            "model_name": "gpt-4-turbo"
        }
        with open(config_manager.config_file, "w") as f:
            yaml.dump(custom_config, f)
            
        config = config_manager.load()
        assert config.openai_api_key == "test-key"
        assert config.model_name == "gpt-4-turbo"

    def test_env_var_override(self, config_manager):
        """Test that environment variables override file config."""
        config_manager.ensure_config_exists()
        
        # File config
        with open(config_manager.config_file, "w") as f:
            yaml.dump({"openai_api_key": "file-key", "model_name": "gpt-3.5"}, f)
            
        # Env var override
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "env-key",
            "MODEL_NAME": "gpt-4-env"
        }):
            config = config_manager.load()
            assert config.openai_api_key == "env-key"
            assert config.model_name == "gpt-4-env"

    def test_aliases_and_variants(self, config_manager):
        """Test that different key variants work in yaml."""
        config_manager.ensure_config_exists()
        
        # Test uppercase in yaml and old key 'model'
        with open(config_manager.config_file, "w") as f:
            yaml.dump({
                "OPENAI_API_KEY": "upper-key",
                "model": "legacy-model",
                "MODEL_NAME_FAST": "fast-model"
            }, f)
            
        config = config_manager.load()
        assert config.openai_api_key == "upper-key"
        assert config.model_name == "legacy-model"
        assert config.model_name_fast == "fast-model"

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
