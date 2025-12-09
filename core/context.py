"""Context management for project-aware agent interactions."""

import os
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import yaml
import aiofiles


HIVE_DIR = ".hive"
PROJECT_CONFIG = "project.yaml"
ARCHITECTURE_FILE = "ARCHITECTURE.md"
ADR_DIR = "docs/adr"


@dataclass
class TechStack:
    """Technology stack configuration."""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    
    def to_context(self) -> str:
        """Format for LLM context."""
        parts = []
        if self.languages:
            parts.append(f"**Sprachen:** {', '.join(self.languages)}")
        if self.frameworks:
            parts.append(f"**Frameworks:** {', '.join(self.frameworks)}")
        if self.databases:
            parts.append(f"**Datenbanken:** {', '.join(self.databases)}")
        if self.tools:
            parts.append(f"**Tools:** {', '.join(self.tools)}")
        return "\n".join(parts) if parts else "Nicht spezifiziert"


@dataclass
class CodeConventions:
    """Code conventions and standards."""
    style_guide: Optional[str] = None
    naming_conventions: dict[str, str] = field(default_factory=dict)
    file_structure: dict[str, str] = field(default_factory=dict)
    testing_strategy: Optional[str] = None
    
    def to_context(self) -> str:
        """Format for LLM context."""
        parts = []
        if self.style_guide:
            parts.append(f"**Style Guide:** {self.style_guide}")
        if self.naming_conventions:
            conv = ", ".join(f"{k}: {v}" for k, v in self.naming_conventions.items())
            parts.append(f"**Naming:** {conv}")
        if self.testing_strategy:
            parts.append(f"**Testing:** {self.testing_strategy}")
        return "\n".join(parts) if parts else "Standard-Konventionen"


@dataclass
class ProjectConfig:
    """Main project configuration stored in .hive/project.yaml."""
    name: str
    description: str = ""
    version: str = "0.1.0"
    
    # Technical details
    tech_stack: TechStack = field(default_factory=TechStack)
    conventions: CodeConventions = field(default_factory=CodeConventions)
    
    # Project structure
    source_dirs: list[str] = field(default_factory=lambda: ["src"])
    test_dirs: list[str] = field(default_factory=lambda: ["tests"])
    doc_dirs: list[str] = field(default_factory=lambda: ["docs"])
    
    # Agent behavior
    default_branch: str = "main"
    ticket_prefix: str = "TICKET"
    auto_commit: bool = True
    
    # Additional context
    important_files: list[str] = field(default_factory=list)
    architecture_notes: str = ""
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tech_stack": {
                "languages": self.tech_stack.languages,
                "frameworks": self.tech_stack.frameworks,
                "databases": self.tech_stack.databases,
                "tools": self.tech_stack.tools,
            },
            "conventions": {
                "style_guide": self.conventions.style_guide,
                "naming_conventions": self.conventions.naming_conventions,
                "file_structure": self.conventions.file_structure,
                "testing_strategy": self.conventions.testing_strategy,
            },
            "structure": {
                "source_dirs": self.source_dirs,
                "test_dirs": self.test_dirs,
                "doc_dirs": self.doc_dirs,
            },
            "agent_config": {
                "default_branch": self.default_branch,
                "ticket_prefix": self.ticket_prefix,
                "auto_commit": self.auto_commit,
            },
            "context": {
                "important_files": self.important_files,
                "architecture_notes": self.architecture_notes,
            },
            "metadata": {
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        """Create from dictionary."""
        tech = data.get("tech_stack", {})
        conv = data.get("conventions", {})
        struct = data.get("structure", {})
        agent = data.get("agent_config", {})
        ctx = data.get("context", {})
        meta = data.get("metadata", {})
        
        return cls(
            name=data.get("name", "Unknown"),
            description=data.get("description", ""),
            version=data.get("version", "0.1.0"),
            tech_stack=TechStack(
                languages=tech.get("languages", []),
                frameworks=tech.get("frameworks", []),
                databases=tech.get("databases", []),
                tools=tech.get("tools", []),
            ),
            conventions=CodeConventions(
                style_guide=conv.get("style_guide"),
                naming_conventions=conv.get("naming_conventions", {}),
                file_structure=conv.get("file_structure", {}),
                testing_strategy=conv.get("testing_strategy"),
            ),
            source_dirs=struct.get("source_dirs", ["src"]),
            test_dirs=struct.get("test_dirs", ["tests"]),
            doc_dirs=struct.get("doc_dirs", ["docs"]),
            default_branch=agent.get("default_branch", "main"),
            ticket_prefix=agent.get("ticket_prefix", "TICKET"),
            auto_commit=agent.get("auto_commit", True),
            important_files=ctx.get("important_files", []),
            architecture_notes=ctx.get("architecture_notes", ""),
            created_at=meta.get("created_at", datetime.now().isoformat()),
            updated_at=meta.get("updated_at", datetime.now().isoformat()),
        )
    
    def to_context(self) -> str:
        """Format full project context for LLM."""
        return f"""## Projekt: {self.name}
{self.description}

### Tech Stack
{self.tech_stack.to_context()}

### Konventionen
{self.conventions.to_context()}

### Projektstruktur
- **Source:** {', '.join(self.source_dirs)}
- **Tests:** {', '.join(self.test_dirs)}
- **Docs:** {', '.join(self.doc_dirs)}

### Wichtige Dateien
{chr(10).join(f'- {f}' for f in self.important_files) if self.important_files else 'Keine spezifiziert'}

### Architektur-Hinweise
{self.architecture_notes if self.architecture_notes else 'Keine'}
"""


class ContextManager:
    """
    Manages project context for agents.
    
    Provides:
    - Project configuration from .hive/project.yaml
    - Architecture documentation from ARCHITECTURE.md
    - ADRs (Architecture Decision Records)
    - Dynamic context based on current work
    """
    
    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.hive_path = self.project_path / HIVE_DIR
        self.config_path = self.hive_path / PROJECT_CONFIG
        self._config: Optional[ProjectConfig] = None
        self._architecture: Optional[str] = None
        self._adrs: dict[str, str] = {}
    
    @property
    def is_initialized(self) -> bool:
        """Check if project has .hive directory."""
        return self.config_path.exists()
    
    async def initialize(
        self,
        name: str,
        description: str = "",
        tech_stack: Optional[dict] = None,
        force: bool = False,
    ) -> ProjectConfig:
        """
        Initialize a new .hive project configuration.
        
        Creates:
        - .hive/project.yaml
        - docs/adr/ directory
        """
        if self.is_initialized and not force:
            raise FileExistsError(
                f"Project already initialized at {self.hive_path}. "
                "Use force=True to overwrite."
            )
        
        # Create directories
        self.hive_path.mkdir(parents=True, exist_ok=True)
        (self.project_path / ADR_DIR).mkdir(parents=True, exist_ok=True)
        
        # Create config
        config = ProjectConfig(
            name=name,
            description=description,
        )
        
        if tech_stack:
            config.tech_stack = TechStack(
                languages=tech_stack.get("languages", []),
                frameworks=tech_stack.get("frameworks", []),
                databases=tech_stack.get("databases", []),
                tools=tech_stack.get("tools", []),
            )
        
        # Auto-detect some settings
        config = await self._auto_detect(config)
        
        # Save config
        await self._save_config(config)
        self._config = config
        
        # Create initial ADR template
        await self._create_adr_template()
        
        return config
    
    async def _auto_detect(self, config: ProjectConfig) -> ProjectConfig:
        """Auto-detect project settings from files."""
        # Detect languages from file extensions
        extensions = set()
        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs"]:
            for _ in self.project_path.glob(pattern):
                ext = pattern.split("*")[-1]
                extensions.add(ext)
                break
        
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
        }
        
        detected_langs = [lang_map[ext] for ext in extensions if ext in lang_map]
        if detected_langs and not config.tech_stack.languages:
            config.tech_stack.languages = detected_langs
        
        # Detect frameworks from config files
        framework_indicators = {
            "package.json": ["React", "Vue", "Next.js", "Express"],
            "requirements.txt": ["Django", "Flask", "FastAPI"],
            "pyproject.toml": ["FastAPI", "Django"],
            "Cargo.toml": ["Actix", "Rocket"],
        }
        
        for config_file, frameworks in framework_indicators.items():
            if (self.project_path / config_file).exists():
                # Could parse file to detect specific framework
                pass
        
        # Detect important files
        important_patterns = [
            "README.md",
            "ARCHITECTURE.md",
            "CONTRIBUTING.md",
            "docker-compose.yml",
            "Dockerfile",
        ]
        
        for pattern in important_patterns:
            if (self.project_path / pattern).exists():
                config.important_files.append(pattern)
        
        return config
    
    async def _save_config(self, config: ProjectConfig) -> None:
        """Save configuration to .hive/project.yaml."""
        config.updated_at = datetime.now().isoformat()
        
        async with aiofiles.open(self.config_path, "w") as f:
            await f.write(yaml.dump(
                config.to_dict(),
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ))
    
    async def _create_adr_template(self) -> None:
        """Create ADR template and index."""
        adr_path = self.project_path / ADR_DIR
        
        # Create template
        template = """# ADR-{number}: {title}

## Status
{status}

## Kontext
{context}

## Entscheidung
{decision}

## Konsequenzen
{consequences}

---
Datum: {date}
Autor: {author}
"""
        
        template_path = adr_path / "TEMPLATE.md"
        if not template_path.exists():
            async with aiofiles.open(template_path, "w") as f:
                await f.write(template)
        
        # Create index
        index = """# Architecture Decision Records

Dieses Verzeichnis enthält Architecture Decision Records (ADRs) für das Projekt.

## Index

| ADR | Titel | Status | Datum |
|-----|-------|--------|-------|
| - | - | - | - |

## Neue ADR erstellen

1. Kopiere `TEMPLATE.md`
2. Benenne die Datei `ADR-XXX-kurzer-titel.md`
3. Fülle die Vorlage aus
4. Aktualisiere diesen Index
"""
        
        index_path = adr_path / "README.md"
        if not index_path.exists():
            async with aiofiles.open(index_path, "w") as f:
                await f.write(index)
    
    async def load(self) -> Optional[ProjectConfig]:
        """Load project configuration."""
        if not self.is_initialized:
            return None
        
        try:
            async with aiofiles.open(self.config_path) as f:
                content = await f.read()
                data = yaml.safe_load(content)
                self._config = ProjectConfig.from_dict(data)
                return self._config
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    async def update(self, **kwargs) -> ProjectConfig:
        """Update project configuration."""
        if not self._config:
            await self.load()
        
        if not self._config:
            raise RuntimeError("Project not initialized")
        
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        
        await self._save_config(self._config)
        return self._config
    
    async def get_architecture(self) -> Optional[str]:
        """Load ARCHITECTURE.md if exists."""
        arch_path = self.project_path / ARCHITECTURE_FILE
        if not arch_path.exists():
            return None
        
        try:
            async with aiofiles.open(arch_path) as f:
                self._architecture = await f.read()
                return self._architecture
        except Exception:
            return None
    
    async def get_adrs(self) -> dict[str, str]:
        """Load all ADRs."""
        adr_path = self.project_path / ADR_DIR
        if not adr_path.exists():
            return {}
        
        adrs = {}
        for adr_file in adr_path.glob("ADR-*.md"):
            try:
                async with aiofiles.open(adr_file) as f:
                    adrs[adr_file.stem] = await f.read()
            except Exception:
                continue
        
        self._adrs = adrs
        return adrs
    
    async def get_full_context(self) -> str:
        """
        Get complete project context for agents.
        
        Combines:
        - Project configuration
        - Architecture documentation
        - Recent ADRs
        """
        parts = []
        
        # Load config if needed
        if not self._config:
            await self.load()
        
        if self._config:
            parts.append(self._config.to_context())
        
        # Architecture
        arch = await self.get_architecture()
        if arch:
            # Truncate if too long
            if len(arch) > 3000:
                arch = arch[:3000] + "\n... (truncated)"
            parts.append(f"## Architektur-Dokumentation\n{arch}")
        
        # Recent ADRs (last 3)
        adrs = await self.get_adrs()
        if adrs:
            recent = list(adrs.items())[-3:]
            adr_summary = "\n\n".join(
                f"### {name}\n{content[:500]}..." 
                if len(content) > 500 else f"### {name}\n{content}"
                for name, content in recent
            )
            parts.append(f"## Aktuelle ADRs\n{adr_summary}")
        
        return "\n\n---\n\n".join(parts) if parts else "Kein Projektkontext verfügbar."
    
    @property
    def config(self) -> Optional[ProjectConfig]:
        """Get current config (may be None if not loaded)."""
        return self._config
