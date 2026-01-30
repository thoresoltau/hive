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

### Voraussetzungen

- **Python 3.10 - 3.13** (3.14+ wird noch nicht unterstützt wegen `onnxruntime`)
- **OpenAI API Key** für Agent-Interaktionen
- Optional: **Tavily API Key** für Web-Suche

### Schnellstart (macOS mit uv)

```bash
# 1. uv installieren (falls nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh
alternativ: brew install uv

# 2. Virtual Environment erstellen und aktivieren
cd /pfad/zu/hive
uv venv # Wenn schon python 3.14 installiert ist -> uv venv --python 3.12
source .venv/bin/activate
# 3. Dependencies installieren
uv pip install -r requirements.txt

# 4. Environment konfigurieren
cp .env.example .env
# Dann OPENAI_API_KEY in .env eintragen
```

### Automatisch via Script (Linux/macOS)

```bash
# Setup-Script ausführen (erstellt venv/ Ordner)
./scripts/setup.sh

# Virtual Environment aktivieren
source venv/bin/activate
```

### Manuell (alle Plattformen)

**Schritt 1: Python Virtual Environment erstellen**

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Hinweis für Ubuntu/Debian:** Falls `venv` fehlt:
> ```bash
> sudo apt install python3-venv python3-pip
> ```

**Schritt 2: Dependencies installieren**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Schritt 3: Environment konfigurieren**

```bash
cp .env.example .env
```

Dann `.env` bearbeiten und mindestens setzen:
- `OPENAI_API_KEY=sk-...` (erforderlich)
- `TAVILY_API_KEY=tvly-...` (optional, für Web-Suche)

### Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage-Report
pytest --cov=. --cov-report=html

# Spezifische Tests
pytest tests/test_file_ops.py -v
```

## 📋 Verwendung

Hive ist jetzt ein projektlokales CLI Tool.

### Setup

Der schnellste Weg zum Start (unterstützt macOS/Linux mit `uv` oder `pip`):

```bash
./scripts/setup.sh
source .venv/bin/activate  # oder source venv/bin/activate
```

Das Skript erledigt alles automatisch:
1. Erstellt Virtual Environment (via `uv` wenn verfügbar)
2. Installiert Dependencies & `hive` CLI
3. Erstellt Config-Templates (`.env` und `~/.hive/config.yaml`)

#### Konfiguration

Trage deinen API-Key ein - entweder global (empfohlen) oder projektlokal:

- **Global:** `~/.hive/config.yaml` (gilt für alle Projekte)
- **Lokal:** `export OPENAI_API_KEY=...`

### 1. In einem Projekt initialisieren

Wechsle in dein Projekt und initialisiere Hive:

```bash
cd /pfad/zu/deinem/projekt
hive init
```

Dies erstellt ein `.hive/` Verzeichnis mit Konfiguration und Ticket-Datenbank.

### 2. Tickets verwalten

```bash
# Interaktiv ein neues Ticket erstellen
hive create-ticket

# Status des Backlogs anzeigen
hive status

# Ticket-Details anzeigen
hive show HIVE-001
```

Die Tickets werden als YAML-Dateien in `.hive/tickets/` gespeichert.

### 3. Agent Swarm starten

```bash
# Alle Tickets im Backlog verarbeiten
hive run

# Limitierte Anzahl an Zyklen
hive run --max-cycles 5

# Nur ein spezifisches Ticket verarbeiten
hive process HIVE-001
```

### 4. RAG & Suche

```bash
# Codebase indexieren
hive index --full

# Semantische Suche
hive search "authentication logic"
```

### 5. Monitoring & Debugging

```bash
# Activity Log (Agenten-Aktionen & Tool-Calls)
hive activity
hive activity --tail 100 --agent backend_dev

# Audit Log (Dateisystem-Operationen)
hive audit
hive audit --all

# Projekt-Kontext (was die Agenten sehen)
hive context
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
