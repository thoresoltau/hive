# 🐝 Hive Agent Swarm

Ein digitales Scrum-Team, das von KI-Agenten betrieben wird. Die Agenten arbeiten autonom zusammen, um Tickets aus einem Backlog zu analysieren, zu verfeinern und **tatsächlich zu implementieren**.

## ✨ Features

- **Echte Code-Generierung** - Agenten können Dateien lesen, erstellen und bearbeiten
- **Git-Integration** - Automatisches Branch-Management und Commits
- **RAG-Suche** - Semantische Codebase-Suche mit ChromaDB + OpenAI Embeddings
- **Web-Suche** - Internet-Recherche via Tavily MCP (Best Practices, Stack Overflow, etc.)
- **Guardrails** - Schutz vor destruktiven Operationen (.git/, .env, etc.)
- **MCP-Integration** - Model Context Protocol für externe Tools (z.B. Context7 Docs)
- **Kontext-Management** - Projektspezifisches Wissen für bessere Entscheidungen
- **Audit-Logging** - Nachvollziehbare File-Operationen
- **Async-Architektur** - Effiziente parallele Verarbeitung

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (Main Loop)                  │
├─────────────────────────────────────────────────────────────┤
│  Backlog Manager  │  Context Manager  │  Message Bus         │
├─────────────────────────────────────────────────────────────┤
│                     Tool Registry                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │  File    │ │   Git    │ │   RAG    │ │   Web    │ │   MCP    │ │
│  │  Tools   │ │  Tools   │ │  Search  │ │  Search  │ │  Tools   │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│                        Agents                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  Scrum   │ │ Product  │ │ Architect│ │ Frontend │ ...    │
│  │  Master  │ │  Owner   │ │          │ │   Dev    │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 👥 Agenten-Rollen

| Agent                  | Verantwortlichkeiten                                             | Tools            |
| ---------------------- | ---------------------------------------------------------------- | ---------------- |
| **Scrum Master**       | Orchestriert Workflow, priorisiert Tickets, löst Blocker         | File, Git (read) |
| **Product Owner**      | Verfeinert Anforderungen, erstellt Tickets, validiert Ergebnisse | File, Git (read) |
| **Software Architect** | Analysiert Codebase, erstellt ADRs, Code-Reviews                 | File, Git (all)  |
| **Frontend Developer** | Implementiert UI-Komponenten, Styling, Tests                     | File, Git (all)  |
| **Backend Developer**  | Implementiert APIs, Business-Logik, Tests                        | File, Git (all)  |

## 🚀 Installation

### Automatisch (empfohlen)

```bash
# Setup-Script ausführen
./scripts/setup.sh

# Virtual Environment aktivieren
source venv/bin/activate
```

### Manuell

```bash
# Voraussetzungen (Ubuntu/Debian)
sudo apt install python3-venv python3-pip

# Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Environment konfigurieren
cp .env.example .env
# Dann OPENAI_API_KEY in .env setzen
```

### Tests ausführen

```bash
# Alle Tests
./scripts/test.sh

# Mit Coverage-Report
./scripts/test.sh --coverage

# Spezifische Tests
./scripts/test.sh tests/test_file_ops.py -v
```

## 📋 Verwendung

### Projekt initialisieren

```bash
# Hive für ein Projekt einrichten
python main.py init --path /pfad/zum/projekt

# Erstellt:
# - .hive/project.yaml  (Projektkonfiguration)
# - docs/adr/           (Architecture Decision Records)
```

### Projektkontext anzeigen

```bash
# Zeigt den Kontext, den Agenten sehen
python main.py context --path /pfad/zum/projekt

# Kontext aktualisieren
python main.py update-context --add-important-file "src/core/api.py"
```

### Ticket erstellen

```bash
python main.py create-ticket
```

Oder manuell eine YAML-Datei in `backlog/tickets/` erstellen:

```yaml
id: HIVE-001
type: feature
title: "Benutzer-Login implementieren"
priority: high
status: backlog
description: |
  Als Benutzer möchte ich mich einloggen können,
  damit ich auf geschützte Bereiche zugreifen kann.
```

### Agent Swarm starten

```bash
# Hauptloop starten (verarbeitet alle Tickets)
python main.py run

# Mit Codebase-Analyse und Tool-Zugriff
python main.py run --codebase /pfad/zum/projekt

# Maximale Zyklen begrenzen
python main.py run --max-cycles 5
```

### Einzelnes Ticket verarbeiten

```bash
python main.py process HIVE-001 --codebase /pfad/zum/projekt
```

### Status anzeigen

```bash
# Backlog-Übersicht
python main.py status

# Ticket-Details
python main.py show HIVE-001
```

### RAG - Semantische Codesuche

```bash
# Codebase indexieren (benötigt OPENAI_API_KEY)
python main.py index --full

# Index-Status anzeigen
python main.py index --status

# Semantisch im Code suchen
python main.py search "wie werden tickets verarbeitet"
python main.py search "authentication logic" -n 10
```

### Audit-Log

```bash
# Letzte File-Operationen anzeigen
python main.py audit

# Mehr Einträge
python main.py audit -n 50

# Alle Einträge
python main.py audit --all
```

## 📁 Projektstruktur

```
hive/
├── agents/
│   ├── base_agent.py        # Abstrakte Basisklasse mit Tool-Support
│   ├── scrum_master.py      # Workflow-Orchestrierung
│   ├── product_owner.py     # Requirements & Validation
│   ├── architect.py         # Technische Analyse & ADRs
│   ├── frontend_dev.py      # Frontend-Implementierung
│   └── backend_dev.py       # Backend-Implementierung
├── core/
│   ├── orchestrator.py      # Hauptsteuerung
│   ├── context.py           # Projekt-Kontext-Management
│   ├── message_bus.py       # Inter-Agent-Kommunikation
│   ├── backlog.py           # Ticket-Management
│   └── models.py            # Pydantic Models
├── tools/
│   ├── base.py              # Tool-Basisklassen & Registry
│   ├── file_ops.py          # File-Operationen (read, write, edit)
│   ├── git_ops.py           # Git-Operationen (branch, commit, etc.)
│   ├── shell_ops.py         # Shell-Befehle (mit Whitelist)
│   ├── guardrails.py        # Sicherheits-Validierung & Audit
│   ├── mcp_ops.py           # MCP Tool-Integration
│   └── rag/                 # RAG-System
│       ├── embeddings.py    # OpenAI Embedding Service
│       ├── chunker.py       # Code-Chunking
│       ├── vectordb.py      # ChromaDB Wrapper
│       ├── indexer.py       # Codebase Indexer
│       └── rag_tool.py      # RAG Search Tool
├── tests/
│   ├── conftest.py          # Shared pytest fixtures
│   ├── test_file_ops.py     # File-Tool Tests
│   ├── test_git_ops.py      # Git-Tool Tests
│   ├── test_context.py      # Context-Management Tests
│   └── test_backlog.py      # Backlog-Management Tests
├── scripts/
│   ├── setup.sh             # Automatisches Setup
│   └── test.sh              # Test-Runner
├── config/
│   ├── agents.yaml          # Agent-Konfigurationen & Prompts
│   ├── rag.yaml             # RAG-Konfiguration
│   └── mcp_servers.yaml     # MCP Server-Konfiguration
├── backlog/
│   ├── index.yaml           # Backlog-Index
│   └── tickets/             # Ticket-Dateien (YAML)
├── main.py                  # CLI Entry Point
├── pytest.ini               # pytest-Konfiguration
├── requirements.txt
├── todo.md                  # Entwicklungs-Roadmap
└── README.md
```

### Struktur bei initialisierten Projekten

```
target-project/
├── .hive/
│   └── project.yaml         # Projektkonfiguration
├── docs/
│   └── adr/
│       ├── README.md        # ADR-Index
│       ├── TEMPLATE.md      # ADR-Vorlage
│       └── ADR-001-*.md     # Architektur-Entscheidungen
└── ARCHITECTURE.md          # (optional) Wird automatisch geladen
```

## 🔄 Workflow

```
1. BACKLOG     → Ticket erstellt, wartet auf Refinement
       ↓
2. REFINED     → Product Owner hat Acceptance Criteria hinzugefügt
       ↓
3. PLANNED     → Architect hat technischen Plan erstellt
       ↓
4. IN_PROGRESS → Developer arbeiten am Ticket
       ↓
5. REVIEW      → Code-Review durch Architect
       ↓
6. DONE        → Product Owner hat validiert
```

## ⚙️ Konfiguration

### Agent-Prompts anpassen

Bearbeite `config/agents.yaml`:

```yaml
agents:
  scrum_master:
    model: "gpt-4o"
    temperature: 0.3
    system_prompt: |
      Du bist ein erfahrener Scrum Master...
```

### Modell wechseln

In `.env`:

```
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o          # Für komplexe Aufgaben
MODEL_NAME_FAST=gpt-4o-mini # Für einfache Aufgaben
```

## � Verfügbare Tools

Alle Agenten haben Zugriff auf Tools über OpenAI Function Calling:

### File-Tools

| Tool             | Beschreibung                                       |
| ---------------- | -------------------------------------------------- |
| `read_file`      | Liest Dateien mit Zeilennummern                    |
| `write_file`     | Erstellt neue Dateien (mit Overwrite-Schutz)       |
| `edit_file`      | Bearbeitet Dateien via String-Ersetzung            |
| `list_directory` | Listet Verzeichnisinhalt (optional rekursiv)       |
| `find_files`     | Sucht Dateien nach Name (Glob) oder Inhalt (Regex) |

### Git-Tools

| Tool                 | Beschreibung                                 |
| -------------------- | -------------------------------------------- |
| `git_status`         | Zeigt geänderte/neue/gelöschte Dateien       |
| `git_branch`         | Erstellt/wechselt Branches                   |
| `git_commit`         | Committed Änderungen (mit Ticket-ID Support) |
| `git_diff`           | Zeigt Änderungen vor dem Commit              |
| `git_log`            | Zeigt Commit-Historie                        |
| `git_current_branch` | Zeigt aktuellen Branch                       |

## 📄 Kontext-Management

Das `.hive/project.yaml` speichert projektspezifischen Kontext:

```yaml
name: "My Project"
description: "Beschreibung des Projekts"

tech_stack:
  languages: [Python, TypeScript]
  frameworks: [FastAPI, React]
  databases: [PostgreSQL]

conventions:
  style_guide: "PEP 8"
  naming_conventions:
    components: PascalCase
    functions: snake_case

structure:
  source_dirs: [src]
  test_dirs: [tests]

agent_config:
  default_branch: main
  ticket_prefix: PROJ
  auto_commit: true

context:
  important_files: [README.md, ARCHITECTURE.md]
  architecture_notes: "Microservices mit Event-Driven Architecture"
```

Dieser Kontext wird automatisch an alle Agent-Prompts angehängt.

## ��️ Erweiterung

### Neuen Agenten hinzufügen

1. Neue Datei in `agents/` erstellen (z.B. `qa_engineer.py`)
2. Von `BaseAgent` erben
3. `process_task()` implementieren
4. In `agents/__init__.py` exportieren
5. In `core/orchestrator.py` registrieren
6. Konfiguration in `config/agents.yaml` hinzufügen

### Neues Tool hinzufügen

1. Tool-Klasse in `tools/` erstellen (erbt von `Tool`)
2. `name`, `description`, `parameters` definieren
3. `execute()` async implementieren
4. In `tools/base.py` → `register_defaults()` registrieren

```python
class MyTool(Tool):
    name = "my_tool"
    description = "Beschreibung für LLM"
    parameters = [
        ToolParameter(name="arg1", type="string", description="...", required=True),
    ]

    async def execute(self, arg1: str) -> ToolResult:
        # Tool-Logik
        return ToolResult(status=ToolResultStatus.SUCCESS, output={"result": "..."})
```

### Implementierte Features

- ✅ **RAG-Integration** - ChromaDB + OpenAI Embeddings für semantische Codesuche
- ✅ **MCP-Integration** - Model Context Protocol (Context7 Docs, Tavily Web Search)
- ✅ **Guardrails** - Protected Paths, Path Traversal Protection, Audit Logging
- ✅ **Shell-Tools** - Whitelist/Blacklist-basierte Befehlsausführung

### Geplante Erweiterungen

- **Tree-sitter Integration** - AST-basierte Code-Analyse (Dependency vorhanden)
- **GitHub/GitLab API** - Automatische PR-Erstellung
- **Jira-Anbindung** - Ticket-Synchronisation
- **Interaktiver Modus** - User-Approval vor destruktiven Änderungen
- **Web UI** - Browser-basierte Oberfläche

## 📝 Lizenz

MIT
