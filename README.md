# 🐝 Hive Agent Swarm

A digital Scrum team powered by AI agents. The agents work autonomously to analyze, refine, and **actually implement** tickets from a backlog.

## ✨ Features

- **Real Code Generation** - Agents can read, create, and edit files
- **Git Integration** - Automatic branch management and commits
- **RAG Search** - Semantic codebase search with ChromaDB + OpenAI Embeddings
- **Web Search** - Internet research via Tavily MCP (Best Practices, Stack Overflow, etc.)
- **Guardrails** - Protection against destructive operations (.git/, .env, etc.)
- **MCP Integration** - Model Context Protocol for external tools (e.g., Context7 Docs)
- **Context Management** - Project-specific knowledge for better decisions
- **Audit Logging** - Traceable file operations
- **Async Architecture** - Efficient parallel processing

## 🏗️ Architecture

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

## 👥 Agent Roles

| Agent                  | Responsibilities                                             | Tools            |
| ---------------------- | ---------------------------------------------------------------- | ---------------- |
| **Scrum Master**       | Orchestrates workflow, prioritizes tickets, resolves blockers      | File, Git (read) |
| **Product Owner**      | Refines requirements, creates tickets, validates results           | File, Git (read) |
| **Software Architect** | Analyzes codebase, creates ADRs, code reviews                      | File, Git (all)  |
| **Frontend Developer** | Implements UI components, styling, tests                           | File, Git (all)  |
| **Backend Developer**  | Implements APIs, business logic, tests                             | File, Git (all)  |

## 🚀 Installation

### Prerequisites

- **Python 3.10 - 3.13** (3.14+ is not supported yet due to `onnxruntime`)
- **OpenAI API Key** for agent interactions
- Optional: **Tavily API Key** for web search

### Quickstart (macOS with uv)

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
alternatively: brew install uv

# 2. Create and activate Virtual Environment
cd /path/to/hive
uv venv # If python 3.14 is already installed -> uv venv --python 3.12
source .venv/bin/activate
# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Then add OPENAI_API_KEY in .env
```

### Automatic via Script (Linux/macOS)

```bash
# Run setup script (creates venv/ directory)
./scripts/setup.sh

# Activate Virtual Environment
source venv/bin/activate
```

### Manual (all platforms)

**Step 1: Create Python Virtual Environment**

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Note for Ubuntu/Debian:** If `venv` is missing:
> ```bash
> sudo apt install python3-venv python3-pip
> ```

**Step 2: Install dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Step 3: Configure environment**

```bash
cp .env.example .env
```

Then edit `.env` and set at least:
- `OPENAI_API_KEY=sk-...` (required)
- `TAVILY_API_KEY=tvly-...` (optional, for web search)

### Run Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=. --cov-report=html

# Specific tests
pytest tests/test_file_ops.py -v
```

## 📋 Usage

Hive is now a project-local CLI Tool.

### Setup

The fastest way to start (supports macOS/Linux with `uv` or `pip`):

```bash
./scripts/setup.sh
source .venv/bin/activate  # or source venv/bin/activate
```

The script does everything automatically:
1. Creates Virtual Environment (via `uv` if available)
2. Installs dependencies & `hive` CLI
3. Creates config templates (`.env` and `~/.hive/config.yaml`)

#### Configuration

Enter your API key - either globally (recommended) or project-local:

- **Global:** `~/.hive/config.yaml` (applies to all projects)
- **Local:** `export OPENAI_API_KEY=...`

### 1. Initialize in a project

Switch to your project and initialize Hive:

```bash
cd /path/to/your/project
hive init
```

This creates a `.hive/` directory with configuration and the ticket database.

### 2. Manage Tickets

```bash
# Interactively create a new ticket
hive create-ticket

# Show the status of the backlog
hive status

# Show ticket details
hive show HIVE-001
```

Tickets are saved as YAML files in `.hive/tickets/`.

### 3. Start Agent Swarm

```bash
# Process all tickets in the backlog
hive run

# Limited number of cycles
hive run --max-cycles 5

# Process only a specific ticket
hive process HIVE-001
```

### 4. RAG & Search

```bash
# Index codebase
hive index --full

# Semantic search
hive search "authentication logic"
```

### 5. Monitoring & Debugging

```bash
# Activity Log (Agent actions & Tool calls)
hive activity
hive activity --tail 100 --agent backend_dev

# Audit Log (File system operations)
hive audit
hive audit --all

# Project Context (what the agents see)
hive context
```

## 📁 Project Structure

```
hive/
├── agents/
│   ├── base_agent.py        # Abstract base class with tool support
│   ├── scrum_master.py      # Workflow orchestration
│   ├── product_owner.py     # Requirements & validation
│   ├── architect.py         # Technical analysis & ADRs
│   ├── frontend_dev.py      # Frontend implementation
│   └── backend_dev.py       # Backend implementation
├── core/
│   ├── orchestrator.py      # Main controller
│   ├── context.py           # Project context management
│   ├── message_bus.py       # Inter-agent communication
│   ├── backlog.py           # Ticket management
│   └── models.py            # Pydantic models
├── tools/
│   ├── base.py              # Tool base classes & registry
│   ├── file_ops.py          # File operations (read, write, edit)
│   ├── git_ops.py           # Git operations (branch, commit, etc.)
│   ├── shell_ops.py         # Shell commands (with whitelist)
│   ├── guardrails.py        # Security validation & audit
│   ├── mcp_ops.py           # MCP tool integration
│   └── rag/                 # RAG system
│       ├── embeddings.py    # OpenAI Embedding Service
│       ├── chunker.py       # Code chunking
│       ├── vectordb.py      # ChromaDB wrapper
│       ├── indexer.py       # Codebase indexer
│       └── rag_tool.py      # RAG Search Tool
├── tests/
│   ├── conftest.py          # Shared pytest fixtures
│   ├── test_file_ops.py     # File tool tests
│   ├── test_git_ops.py      # Git tool tests
│   ├── test_context.py      # Context management tests
│   └── test_backlog.py      # Backlog management tests
├── scripts/
│   ├── setup.sh             # Automatic setup
│   └── test.sh              # Test runner
├── config/
│   ├── agents.yaml          # Agent configurations & prompts
│   ├── rag.yaml             # RAG configuration
│   └── mcp_servers.yaml     # MCP server configuration
├── backlog/
│   ├── index.yaml           # Backlog index
│   └── tickets/             # Ticket files (YAML)
├── main.py                  # CLI Entry Point
├── pytest.ini               # pytest configuration
├── requirements.txt
├── todo.md                  # Development roadmap
└── README.md
```

### Structure in initialized projects

```
target-project/
├── .hive/
│   └── project.yaml         # Project configuration
├── docs/
│   └── adr/
│       ├── README.md        # ADR index
│       ├── TEMPLATE.md      # ADR template
│       └── ADR-001-*.md     # Architecture Decision Records
└── ARCHITECTURE.md          # (optional) loaded automatically
```

## 🔄 Workflow

```
1. BACKLOG     → Ticket created, waiting for refinement
       ↓
2. REFINED     → Product Owner added acceptance criteria
       ↓
3. PLANNED     → Architect created a technical plan
       ↓
4. IN_PROGRESS → Developers working on the ticket
       ↓
5. REVIEW      → Code review by Architect
       ↓
6. DONE        → Product Owner validated the result
```

## ⚙️ Configuration

### Adapting Agent Prompts

Edit `config/agents.yaml`:

```yaml
agents:
  scrum_master:
    model: "gpt-4o"
    temperature: 0.3
    system_prompt: |
      You are an experienced Scrum Master...
```

### Switching Provider & Model (LiteLLM)

Hive uses `litellm` in the background and natively supports **OpenAI**, **Anthropic**, **Gemini**, **Mistral**, and many other models. The desired model is defined using a provider prefix in `.env`, and LiteLLM handles the correct translation.

**1. OpenAI (Default)**
```env
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o          # For complex tasks
MODEL_NAME_FAST=gpt-4o-mini # For simple tasks (e.g., commit messages)
```

**2. Google Gemini**
```env
GEMINI_API_KEY=AIzaSy...
MODEL_NAME=gemini/gemini-1.5-pro     # For complex tasks
MODEL_NAME_FAST=gemini/gemini-1.5-flash
```

**3. Anthropic Claude**
```env
ANTHROPIC_API_KEY=sk-ant-...
MODEL_NAME=anthropic/claude-3-5-sonnet-20241022
MODEL_NAME_FAST=anthropic/claude-3-haiku-20240307
```

## 🧰 Available Tools

All agents have access to tools via OpenAI Function Calling:

### File Tools

| Tool             | Description                                        |
| ---------------- | -------------------------------------------------- |
| `read_file`      | Reads files with line numbers                      |
| `write_file`     | Creates new files (with overwrite protection)      |
| `edit_file`      | Edits files via string replacement                 |
| `list_directory` | Lists directory contents (optionally recursively)  |
| `find_files`     | Searches files by name (Glob) or content (Regex)   |

### Git Tools

| Tool                 | Description                                    |
| -------------------- | ---------------------------------------------- |
| `git_status`         | Shows changed/new/deleted files                |
| `git_branch`         | Creates/switches branches                      |
| `git_commit`         | Commits changes (with Ticket-ID support)       |
| `git_diff`           | Shows changes prior to committing              |
| `git_log`            | Shows commit history                           |
| `git_current_branch` | Shows current branch                           |

## 📄 Context Management

The `.hive/project.yaml` stores project-specific context:

```yaml
name: "My Project"
description: "Description of the project"

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
  architecture_notes: "Microservices with Event-Driven Architecture"
```

This context is automatically appended to all agent prompts.

## 🛠️ Extension

### Adding a new Agent

1. Create a new file in `agents/` (e.g., `qa_engineer.py`)
2. Inherit from `BaseAgent`
3. Implement `process_task()`
4. Export in `agents/__init__.py`
5. Register in `core/orchestrator.py`
6. Add configuration to `config/agents.yaml`

### Adding a new Tool

1. Create a tool class in `tools/` (inherits from `Tool`)
2. Define `name`, `description`, `parameters`
3. Implement asynchronous `execute()`
4. Register in `tools/base.py` → `register_defaults()`

```python
class MyTool(Tool):
    name = "my_tool"
    description = "Description for LLM"
    parameters = [
        ToolParameter(name="arg1", type="string", description="...", required=True),
    ]

    async def execute(self, arg1: str) -> ToolResult:
        # Tool logic
        return ToolResult(status=ToolResultStatus.SUCCESS, output={"result": "..."})
```

### Implemented Features

- ✅ **RAG Integration** - ChromaDB + OpenAI Embeddings for semantic code search
- ✅ **MCP Integration** - Model Context Protocol (Context7 Docs, Tavily Web Search)
- ✅ **Guardrails** - Protected Paths, Path Traversal Protection, Audit Logging
- ✅ **Shell Tools** - Whitelist/Blacklist based command execution

### Planned Extensions

- **Tree-sitter Integration** - AST-based code analysis (dependency available)
- **GitHub/GitLab API** - Automatic PR creation
- **Jira Integration** - Ticket synchronization
- **Interactive Mode** - User approval before destructive changes
- **Web UI** - Browser-based interface

## 📝 License

GTFO MIT
