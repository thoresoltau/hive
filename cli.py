#!/usr/bin/env python3
"""
Hive Agent Swarm - A digital Scrum team powered by AI agents.

Usage:
    hive init                  # Initialize Hive in current directory
    hive create-ticket         # Create a new ticket
    hive run                   # Run the agent swarm
    hive process TICKET-ID     # Process a specific ticket
    hive status                # Show backlog status
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

app = typer.Typer(help="Hive Agent Swarm - Digital Scrum Team powered by AI agents")
console = Console()

# Package directory (where default configs are stored)
PACKAGE_DIR = Path(__file__).parent


class HiveNotInitializedError(Exception):
    """Raised when trying to use Hive in a non-initialized directory."""
    pass


def get_project_path() -> Path:
    """
    Get project root (containing .hive/).
    
    Searches from current directory upwards.
    """
    cwd = Path.cwd()
    
    # Check current directory
    if (cwd / ".hive").exists():
        return cwd
    
    # Search parent directories
    for parent in cwd.parents:
        if (parent / ".hive").exists():
            return parent
    
    raise HiveNotInitializedError(
        "Kein Hive-Projekt gefunden. Führe 'hive init' aus."
    )


def get_hive_dir() -> Path:
    """Get .hive directory for current project."""
    return get_project_path() / ".hive"


def get_tickets_dir() -> Path:
    """Get tickets directory for current project."""
    return get_hive_dir() / "tickets"


def get_config_path() -> Path:
    """Get agents.yaml config path (from package)."""
    return PACKAGE_DIR / "config" / "agents.yaml"


def require_initialized(func):
    """Decorator to ensure Hive is initialized before running command."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            get_project_path()
            return func(*args, **kwargs)
        except HiveNotInitializedError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(1)
    return wrapper


# === Lazy imports to avoid circular dependencies ===

def get_orchestrator() -> "Orchestrator":
    """Create orchestrator instance for current project."""
    from core.orchestrator import Orchestrator
    
    project_path = get_project_path()
    return Orchestrator(
        backlog_path=get_tickets_dir().parent,  # .hive/
        config_path=get_config_path(),
        codebase_path=str(project_path),
    )


def get_backlog_manager() -> "BacklogManager":
    """Get backlog manager for current project."""
    from core.backlog import BacklogManager
    return BacklogManager(get_hive_dir())


def get_context_manager() -> "ContextManager":
    """Get context manager for current project."""
    from core.context import ContextManager
    return ContextManager(get_project_path())


# === Commands ===

@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """
    Initialize Hive in the current directory.
    
    Creates .hive/ with project configuration.
    """
    from core.context import ContextManager
    
    project_path = Path.cwd()
    hive_dir = project_path / ".hive"
    
    if hive_dir.exists() and not force:
        console.print(f"[yellow]⚠ Hive bereits initialisiert in {project_path}[/yellow]")
        console.print("Nutze --force zum Überschreiben.")
        raise typer.Exit(1)
    
    # Get project info interactively
    project_name = project_path.name
    project_name = Prompt.ask("Projektname", default=project_name)
    description = Prompt.ask("Beschreibung", default="")
    
    # Get tech stack
    console.print("\n[bold]Tech Stack[/bold] (komma-separiert, leer für Auto-Detect)")
    languages = Prompt.ask("Sprachen", default="")
    frameworks = Prompt.ask("Frameworks", default="")
    
    tech_stack = {}
    if languages:
        tech_stack["languages"] = [l.strip() for l in languages.split(",")]
    if frameworks:
        tech_stack["frameworks"] = [f.strip() for f in frameworks.split(",")]
    
    async def _init():
        ctx = ContextManager(project_path)
        config = await ctx.initialize(
            name=project_name,
            description=description,
            tech_stack=tech_stack if tech_stack else None,
            force=force,
        )
        
        # Create tickets directory
        tickets_dir = hive_dir / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(f"\n[green]✓ Hive initialisiert![/green]")
        console.print(f"  Projekt: {project_path}")
        console.print(f"  Config: {hive_dir / 'project.yaml'}")
        console.print(f"  Tickets: {tickets_dir}")
        
        if config.tech_stack.languages:
            console.print(f"\n[bold]Erkannt:[/bold]")
            console.print(f"  Sprachen: {', '.join(config.tech_stack.languages)}")
    
    asyncio.run(_init())


@app.command()
@require_initialized
def run(
    max_cycles: int = typer.Option(10, help="Maximum number of cycles to run"),
):
    """Run the Hive Agent Swarm on the current project."""
    async def _run():
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        await orchestrator.run(max_cycles=max_cycles)
    
    project = get_project_path()
    console.print(f"[blue]🐝 Starting Hive on {project}[/blue]\n")
    asyncio.run(_run())


@app.command()
@require_initialized
def process(
    ticket_id: str = typer.Argument(..., help="Ticket ID to process"),
):
    """Process a specific ticket through the workflow."""
    async def _process():
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        response = await orchestrator.process_ticket(ticket_id)
        
        console.print(f"\n[bold]Result:[/bold] {response.action_taken}")
        console.print(f"[bold]Message:[/bold] {response.message}")
    
    asyncio.run(_process())


@app.command("create-ticket")
@require_initialized
def create_ticket():
    """Create a new ticket interactively."""
    from core.models import TicketType, Priority
    
    console.print("\n[bold blue]Neues Ticket erstellen[/bold blue]\n")
    
    # Auto-generate ticket ID
    tickets_dir = get_tickets_dir()
    existing = list(tickets_dir.glob("*.yaml"))
    next_num = len(existing) + 1
    
    # Get project prefix from config
    try:
        ctx = get_context_manager()
        prefix = "HIVE"  # TODO: Get from project config
    except Exception:
        prefix = "HIVE"
    
    default_id = f"{prefix}-{next_num:03d}"
    
    ticket_id = Prompt.ask("Ticket ID", default=default_id)
    title = Prompt.ask("Titel")
    
    console.print("\nTypen: feature, bug, refactor, chore, spike")
    ticket_type = Prompt.ask("Typ", default="feature")
    
    console.print("\nPrioritäten: critical, high, medium, low")
    priority = Prompt.ask("Priorität", default="medium")
    
    console.print("\nBeschreibung (leer lassen = Ende):")
    description_lines = []
    while True:
        line = input()
        if not line:
            break
        description_lines.append(line)
    description = "\n".join(description_lines)
    
    # Create ticket file
    ticket_content = f"""id: {ticket_id}
type: {ticket_type}
title: "{title}"
priority: {priority}
status: backlog
description: |
  {description.replace(chr(10), chr(10) + '  ')}
"""
    
    ticket_file = tickets_dir / f"{ticket_id}.yaml"
    ticket_file.write_text(ticket_content)
    
    console.print(f"\n[green]✅ Ticket {ticket_id} erstellt![/green]")
    console.print(f"   Datei: {ticket_file}")


@app.command()
@require_initialized
def status():
    """Show current backlog status."""
    tickets_dir = get_tickets_dir()
    
    if not tickets_dir.exists():
        console.print("[yellow]Keine Tickets vorhanden.[/yellow]")
        return
    
    ticket_files = list(tickets_dir.glob("*.yaml"))
    
    if not ticket_files:
        console.print("[yellow]Keine Tickets im Backlog.[/yellow]")
        return
    
    import yaml
    
    table = Table(title=f"Backlog ({get_project_path().name})")
    table.add_column("ID", style="cyan")
    table.add_column("Titel", style="white")
    table.add_column("Typ", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Priorität", style="yellow")
    
    for ticket_file in sorted(ticket_files):
        with open(ticket_file) as f:
            ticket = yaml.safe_load(f)
        
        title = ticket.get("title", "")
        if len(title) > 40:
            title = title[:37] + "..."
        
        table.add_row(
            ticket.get("id", "?"),
            title,
            ticket.get("type", "?"),
            ticket.get("status", "?"),
            ticket.get("priority", "?"),
        )
    
    console.print()
    console.print(table)


@app.command()
@require_initialized
def show(ticket_id: str = typer.Argument(..., help="Ticket ID to show")):
    """Show detailed ticket information."""
    import yaml
    
    ticket_file = get_tickets_dir() / f"{ticket_id}.yaml"
    
    if not ticket_file.exists():
        console.print(f"[red]Ticket {ticket_id} nicht gefunden.[/red]")
        raise typer.Exit(1)
    
    with open(ticket_file) as f:
        ticket = yaml.safe_load(f)
    
    console.print(f"\n[bold cyan]Ticket: {ticket.get('id')}[/bold cyan]")
    console.print(f"[bold]Titel:[/bold] {ticket.get('title')}")
    console.print(f"[bold]Typ:[/bold] {ticket.get('type')}")
    console.print(f"[bold]Status:[/bold] {ticket.get('status')}")
    console.print(f"[bold]Priorität:[/bold] {ticket.get('priority')}")
    console.print(f"\n[bold]Beschreibung:[/bold]\n{ticket.get('description', '')}")


@app.command()
@require_initialized
def index(
    full: bool = typer.Option(False, "--full", "-f", help="Force full re-index"),
    status_only: bool = typer.Option(False, "--status", "-s", help="Show index status only"),
):
    """Index codebase for semantic search (RAG)."""
    from tools.rag import CodebaseIndexer, EmbeddingService, VectorDB
    
    project_path = get_project_path()
    hive_dir = get_hive_dir()
    
    async def _index():
        if status_only:
            vectordb = VectorDB(persist_dir=str(hive_dir / "vectordb"))
            indexer = CodebaseIndexer(
                workspace_path=str(project_path),
                vectordb=vectordb,
            )
            status = indexer.get_status()
            console.print("\n[bold blue]RAG Index Status[/bold blue]")
            console.print(f"  Projekt: {status['workspace_path']}")
            console.print(f"  Letzte Indexierung: {status['last_indexed'] or 'Nie'}")
            console.print(f"  Indizierte Dateien: {status['indexed_files']}")
            console.print(f"  Chunks: {status['total_chunks']}")
            return
        
        embedding_service = EmbeddingService()
        vectordb = VectorDB(persist_dir=str(hive_dir / "vectordb"))
        indexer = CodebaseIndexer(
            workspace_path=str(project_path),
            embedding_service=embedding_service,
            vectordb=vectordb,
        )
        
        console.print(f"\n[bold blue]Indexiere: {project_path}[/bold blue]")
        
        def progress(file_path: str, current: int, total: int):
            console.print(f"  [{current}/{total}] {Path(file_path).name}")
        
        if full:
            console.print("[yellow]Vollständige Neuindexierung...[/yellow]")
            result = await indexer.index_full(progress_callback=progress)
        else:
            result = await indexer.index_changed_files(progress_callback=progress)
        
        console.print(f"\n[green]✓ Indexierung abgeschlossen![/green]")
        if full:
            console.print(f"  Dateien: {result['files_indexed']}")
        else:
            console.print(f"  Geändert: {result['files_changed']}")
            console.print(f"  Gelöscht: {result['files_deleted']}")
        console.print(f"  Chunks: {result['chunks_created']}")
    
    asyncio.run(_index())


@app.command()
@require_initialized
def search(
    query: str = typer.Argument(..., help="Search query"),
    n_results: int = typer.Option(5, "-n", help="Number of results"),
):
    """Search indexed codebase semantically."""
    from tools.rag import RAGSearchTool
    
    project_path = get_project_path()
    
    async def _search():
        tool = RAGSearchTool(workspace_path=str(project_path))
        result = await tool.execute(query=query, n_results=n_results)
        
        if result.success:
            console.print(f"\n[bold blue]Suche:[/bold blue] {query}\n")
            console.print(result.output)
        else:
            console.print(f"[red]Fehler: {result.error}[/red]")
    
    asyncio.run(_search())


@app.command()
@require_initialized
def audit(
    tail: int = typer.Option(20, "-n", "--tail", help="Number of entries to show"),
    all_entries: bool = typer.Option(False, "--all", "-a", help="Show all entries"),
):
    """Show audit log of file operations."""
    from tools.guardrails import AuditLogger
    
    project_path = get_project_path()
    log_file = get_hive_dir() / "audit.log"
    
    if not log_file.exists():
        console.print("[yellow]Kein Audit-Log vorhanden.[/yellow]")
        return
    
    logger = AuditLogger(workspace_path=str(project_path))
    
    if all_entries:
        with open(log_file) as f:
            entries = f.readlines()
    else:
        entries = logger.get_recent(tail)
    
    if not entries:
        console.print("[yellow]Audit-Log ist leer.[/yellow]")
        return
    
    console.print(f"\n[bold blue]Audit Log[/bold blue] ({len(entries)} Einträge)\n")
    
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        
        if "[blocked]" in entry:
            console.print(f"[red]{entry}[/red]")
        elif "[error]" in entry:
            console.print(f"[yellow]{entry}[/yellow]")
        elif "[success]" in entry:
            console.print(f"[green]{entry}[/green]")
        else:
            console.print(entry)


@app.command()
@require_initialized
def context():
    """Show project context that will be provided to agents."""
    async def _context():
        ctx = get_context_manager()
        full_context = await ctx.get_full_context()
        console.print(full_context)
    
    asyncio.run(_context())


if __name__ == "__main__":
    app()
