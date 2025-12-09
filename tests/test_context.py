"""Tests for context management."""

import pytest
from pathlib import Path

from core.context import (
    ContextManager,
    ProjectConfig,
    TechStack,
    CodeConventions,
)


class TestProjectConfig:
    """Tests for ProjectConfig dataclass."""

    def test_create_default_config(self):
        """Should create config with defaults."""
        config = ProjectConfig(name="Test")
        
        assert config.name == "Test"
        assert config.version == "0.1.0"
        assert config.default_branch == "main"
        assert config.source_dirs == ["src"]

    def test_config_to_dict(self):
        """Should serialize to dictionary."""
        config = ProjectConfig(
            name="Test",
            description="A test project",
        )
        
        data = config.to_dict()
        
        assert data["name"] == "Test"
        assert data["description"] == "A test project"
        assert "tech_stack" in data
        assert "metadata" in data

    def test_config_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "name": "Test",
            "description": "A test project",
            "tech_stack": {
                "languages": ["Python"],
                "frameworks": ["FastAPI"],
            },
        }
        
        config = ProjectConfig.from_dict(data)
        
        assert config.name == "Test"
        assert config.tech_stack.languages == ["Python"]
        assert config.tech_stack.frameworks == ["FastAPI"]

    def test_config_to_context(self):
        """Should format for LLM context."""
        config = ProjectConfig(
            name="Test Project",
            description="A test project",
        )
        config.tech_stack.languages = ["Python"]
        
        context = config.to_context()
        
        assert "Test Project" in context
        assert "Python" in context


class TestTechStack:
    """Tests for TechStack dataclass."""

    def test_tech_stack_to_context(self):
        """Should format tech stack for context."""
        stack = TechStack(
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI"],
            databases=["PostgreSQL"],
        )
        
        context = stack.to_context()
        
        assert "Python" in context
        assert "TypeScript" in context
        assert "FastAPI" in context
        assert "PostgreSQL" in context

    def test_empty_tech_stack(self):
        """Should handle empty tech stack."""
        stack = TechStack()
        
        context = stack.to_context()
        
        assert "Nicht spezifiziert" in context


class TestContextManager:
    """Tests for ContextManager."""

    @pytest.fixture
    def manager(self, temp_dir):
        return ContextManager(temp_dir)

    async def test_not_initialized(self, manager):
        """Should report not initialized."""
        assert not manager.is_initialized

    async def test_initialize_project(self, manager, temp_dir):
        """Should initialize project."""
        config = await manager.initialize(
            name="Test Project",
            description="A test",
        )
        
        assert manager.is_initialized
        assert config.name == "Test Project"
        assert (temp_dir / ".hive" / "project.yaml").exists()

    async def test_initialize_creates_adr_dir(self, manager, temp_dir):
        """Should create ADR directory."""
        await manager.initialize(name="Test")
        
        assert (temp_dir / "docs" / "adr").exists()
        assert (temp_dir / "docs" / "adr" / "TEMPLATE.md").exists()
        assert (temp_dir / "docs" / "adr" / "README.md").exists()

    async def test_initialize_with_tech_stack(self, manager):
        """Should accept tech stack."""
        config = await manager.initialize(
            name="Test",
            tech_stack={
                "languages": ["Python"],
                "frameworks": ["Django"],
            },
        )
        
        assert config.tech_stack.languages == ["Python"]
        assert config.tech_stack.frameworks == ["Django"]

    async def test_initialize_force_overwrite(self, manager):
        """Should overwrite with force flag."""
        await manager.initialize(name="First")
        config = await manager.initialize(name="Second", force=True)
        
        assert config.name == "Second"

    async def test_initialize_no_overwrite_by_default(self, manager):
        """Should not overwrite without force flag."""
        await manager.initialize(name="First")
        
        with pytest.raises(FileExistsError):
            await manager.initialize(name="Second")

    async def test_load_config(self, manager):
        """Should load saved config."""
        await manager.initialize(name="Test Project")
        
        # Create new manager instance
        new_manager = ContextManager(manager.project_path)
        config = await new_manager.load()
        
        assert config is not None
        assert config.name == "Test Project"

    async def test_update_config(self, manager):
        """Should update config fields."""
        await manager.initialize(name="Test")
        
        updated = await manager.update(description="Updated description")
        
        assert updated.description == "Updated description"

    async def test_get_architecture(self, manager, temp_dir):
        """Should load ARCHITECTURE.md if exists."""
        await manager.initialize(name="Test")
        
        # Create architecture file
        arch_content = "# Architecture\n\nThis is the architecture."
        (temp_dir / "ARCHITECTURE.md").write_text(arch_content)
        
        arch = await manager.get_architecture()
        
        assert arch is not None
        assert "Architecture" in arch

    async def test_get_architecture_missing(self, manager):
        """Should return None if no ARCHITECTURE.md."""
        await manager.initialize(name="Test")
        
        arch = await manager.get_architecture()
        
        assert arch is None

    async def test_get_adrs(self, manager, temp_dir):
        """Should load ADRs."""
        await manager.initialize(name="Test")
        
        # Create an ADR
        adr_content = "# ADR-001: Test Decision\n\nWe decided to test."
        (temp_dir / "docs" / "adr" / "ADR-001-test.md").write_text(adr_content)
        
        adrs = await manager.get_adrs()
        
        assert len(adrs) == 1
        assert "ADR-001-test" in adrs

    async def test_get_full_context(self, manager, temp_dir):
        """Should combine all context sources."""
        await manager.initialize(
            name="Test Project",
            description="A test project",
        )
        
        # Add architecture
        (temp_dir / "ARCHITECTURE.md").write_text("# Architecture")
        
        context = await manager.get_full_context()
        
        assert "Test Project" in context
        assert "Architecture" in context

    async def test_auto_detect_languages(self, manager, temp_dir):
        """Should auto-detect languages from file extensions."""
        # Create some Python files
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("print('hello')")
        
        config = await manager.initialize(name="Test")
        
        # Should detect Python
        assert "Python" in config.tech_stack.languages

    async def test_auto_detect_important_files(self, manager, temp_dir):
        """Should detect important files."""
        # Create README
        (temp_dir / "README.md").write_text("# Project")
        
        config = await manager.initialize(name="Test")
        
        assert "README.md" in config.important_files
