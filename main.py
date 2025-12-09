#!/usr/bin/env python3
"""
Hive Agent Swarm - A digital Scrum team powered by AI agents.

Usage:
    python main.py run                    # Run the main loop
    python main.py create-ticket          # Create a new ticket interactively
    python main.py process TICKET-ID      # Process a specific ticket
    python main.py status                 # Show backlog status
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from core.orchestrator import Orchestrator
from core.backlog import BacklogManager
from core.models import TicketType, Priority
from core.context import ContextManager

app = typer.Typer(help="Hive Agent Swarm - Digital Scrum Team")
console = Console()

# Paths
BASE_DIR = Path(__file__).parent
BACKLOG_PATH = BASE_DIR / "backlog"
CONFIG_PATH = BASE_DIR / "config" / "agents.yaml"


def get_orchestrator(codebase_path: str = None) -> Orchestrator:
    """Create orchestrator instance."""
    return Orchestrator(
        backlog_path=BACKLOG_PATH,
        config_path=CONFIG_PATH,
        codebase_path=codebase_path,
    )


@app.command()
def run(
    max_cycles: int = typer.Option(10, help="Maximum number of cycles to run"),
    codebase: str = typer.Option(None, help="Path to codebase for analysis"),
):
    """Run the Hive Agent Swarm main loop."""
    async def _run():
        orchestrator = get_orchestrator(codebase)
        await orchestrator.initialize()
        await orchestrator.run(max_cycles=max_cycles)
    
    asyncio.run(_run())


@app.command()
def process(
    ticket_id: str = typer.Argument(..., help="Ticket ID to process"),
    codebase: str = typer.Option(None, help="Path to codebase"),
):
    """Process a specific ticket through the workflow."""
    async def _process():
        orchestrator = get_orchestrator(codebase)
        await orchestrator.initialize()
        response = await orchestrator.process_ticket(ticket_id)
        
        console.print(f"\n[bold]Result:[/bold] {response.action_taken}")
        console.print(f"[bold]Message:[/bold] {response.message}")
    
    asyncio.run(_process())


@app.command("create-ticket")
def create_ticket():
    """Create a new ticket interactively."""
    console.print("\n[bold blue]Create New Ticket[/bold blue]\n")
    
    # Get ticket details
    ticket_id = Prompt.ask("Ticket ID", default="HIVE-001")
    title = Prompt.ask("Title")
    
    console.print("\nTypes: feature, bug, refactor, chore, spike")
    ticket_type = Prompt.ask("Type", default="feature")
    
    console.print("\nPriorities: critical, high, medium, low")
    priority = Prompt.ask("Priority", default="medium")
    
    console.print("\nDescription (end with empty line):")
    description_lines = []
    while True:
        line = input()
        if not line:
            break
        description_lines.append(line)
    description = "\n".join(description_lines)
    
    async def _create():
        backlog = BacklogManager(BACKLOG_PATH)
        await backlog.initialize()
        
        ticket = await backlog.create_ticket(
            id=ticket_id,
            title=title,
            description=description,
            type=ticket_type,
            priority=priority,
        )
        
        console.print(f"\n[green]✅ Ticket {ticket.id} created successfully![/green]")
        console.print(f"   Status: {ticket.status.value}")
        console.print(f"   File: backlog/tickets/{ticket.id}.yaml")
    
    asyncio.run(_create())


@app.command()
def status():
    """Show current backlog status."""
    async def _status():
        backlog = BacklogManager(BACKLOG_PATH)
        await backlog.initialize()
        
        tickets = backlog.get_all_tickets()
        
        if not tickets:
            console.print("\n[yellow]No tickets in backlog.[/yellow]")
            return
        
        # Create status table
        table = Table(title="Backlog Status")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Type", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Priority", style="yellow")
        table.add_column("Points", style="magenta")
        
        for ticket in tickets:
            points = str(ticket.estimation.story_points) if ticket.estimation.story_points else "-"
            table.add_row(
                ticket.id,
                ticket.title[:40] + "..." if len(ticket.title) > 40 else ticket.title,
                ticket.type.value,
                ticket.status.value,
                ticket.priority.value,
                points,
            )
        
        console.print()
        console.print(table)
        
        # Summary
        summary = backlog.get_sprint_summary()
        console.print(f"\n[bold]Sprint {summary['sprint']}:[/bold]")
        for status, count in summary["status_breakdown"].items():
            if count > 0:
                console.print(f"  {status}: {count}")
    
    asyncio.run(_status())


@app.command()
def show(ticket_id: str = typer.Argument(..., help="Ticket ID to show")):
    """Show detailed ticket information."""
    async def _show():
        backlog = BacklogManager(BACKLOG_PATH)
        await backlog.initialize()
        
        ticket = backlog.get_ticket(ticket_id)
        
        if not ticket:
            console.print(f"[red]Ticket {ticket_id} not found.[/red]")
            return
        
        console.print(f"\n[bold cyan]Ticket: {ticket.id}[/bold cyan]")
        console.print(f"[bold]Title:[/bold] {ticket.title}")
        console.print(f"[bold]Type:[/bold] {ticket.type.value}")
        console.print(f"[bold]Status:[/bold] {ticket.status.value}")
        console.print(f"[bold]Priority:[/bold] {ticket.priority.value}")
        
        console.print(f"\n[bold]Description:[/bold]\n{ticket.description}")
        
        if ticket.user_story:
            console.print(f"\n[bold]User Story:[/bold]")
            console.print(f"  Als {ticket.user_story.as_a}")
            console.print(f"  möchte ich {ticket.user_story.i_want}")
            console.print(f"  damit {ticket.user_story.so_that}")
        
        if ticket.acceptance_criteria:
            console.print(f"\n[bold]Acceptance Criteria:[/bold]")
            for i, ac in enumerate(ticket.acceptance_criteria, 1):
                console.print(f"  {i}. {ac}")
        
        if ticket.technical_context.affected_areas:
            console.print(f"\n[bold]Technical Context:[/bold]")
            console.print(f"  Areas: {', '.join(ticket.technical_context.affected_areas)}")
            
            if ticket.technical_context.related_files:
                console.print(f"  Related Files:")
                for rf in ticket.technical_context.related_files:
                    console.print(f"    - {rf.path}: {rf.reason}")
        
        if ticket.comments:
            console.print(f"\n[bold]Comments:[/bold]")
            for comment in ticket.comments[-5:]:  # Last 5 comments
                timestamp = comment.timestamp.strftime("%Y-%m-%d %H:%M")
                console.print(f"  [{timestamp}] {comment.agent}: {comment.message[:100]}")
    
    asyncio.run(_show())


@app.command()
def init(
    name: str = typer.Option(None, help="Project name"),
    path: str = typer.Option(".", help="Path to project root"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """
    Initialize Hive for a project.
    
    Creates .hive/project.yaml with project configuration.
    """
    async def _init():
        project_path = Path(path).resolve()
        
        if not project_path.exists():
            console.print(f"[red]Path does not exist: {project_path}[/red]")
            raise typer.Exit(1)
        
        ctx = ContextManager(project_path)
        
        if ctx.is_initialized and not force:
            console.print(f"[yellow]Project already initialized at {project_path}[/yellow]")
            console.print("Use --force to overwrite.")
            raise typer.Exit(1)
        
        # Get project name
        project_name = name or project_path.name
        project_name = Prompt.ask("Project name", default=project_name)
        
        # Get description
        description = Prompt.ask("Description", default="")
        
        # Get tech stack
        console.print("\n[bold]Tech Stack[/bold] (comma-separated, leave empty to auto-detect)")
        languages = Prompt.ask("Languages", default="")
        frameworks = Prompt.ask("Frameworks", default="")
        databases = Prompt.ask("Databases", default="")
        
        tech_stack = {}
        if languages:
            tech_stack["languages"] = [l.strip() for l in languages.split(",")]
        if frameworks:
            tech_stack["frameworks"] = [f.strip() for f in frameworks.split(",")]
        if databases:
            tech_stack["databases"] = [d.strip() for d in databases.split(",")]
        
        console.print("\n[bold]Initializing...[/bold]")
        
        config = await ctx.initialize(
            name=project_name,
            description=description,
            tech_stack=tech_stack if tech_stack else None,
            force=force,
        )
        
        console.print(f"\n[green]✓ Project initialized![/green]")
        console.print(f"  Config: {ctx.config_path}")
        console.print(f"  ADRs: {project_path / 'docs/adr'}")
        console.print(f"\n[bold]Detected:[/bold]")
        console.print(f"  Languages: {', '.join(config.tech_stack.languages) or 'none'}")
        console.print(f"  Important files: {', '.join(config.important_files) or 'none'}")
        console.print(f"\n[dim]Edit .hive/project.yaml to customize.[/dim]")
    
    asyncio.run(_init())


@app.command()
def context(
    path: str = typer.Option(".", help="Path to project root"),
):
    """Show project context that will be provided to agents."""
    async def _context():
        project_path = Path(path).resolve()
        ctx = ContextManager(project_path)
        
        if not ctx.is_initialized:
            console.print(f"[yellow]Project not initialized. Run 'hive init' first.[/yellow]")
            raise typer.Exit(1)
        
        full_context = await ctx.get_full_context()
        console.print(full_context)
    
    asyncio.run(_context())


@app.command("update-context")
def update_context(
    path: str = typer.Option(".", help="Path to project root"),
    architecture_notes: str = typer.Option(None, help="Update architecture notes"),
    add_important_file: str = typer.Option(None, help="Add an important file"),
):
    """Update project context configuration."""
    async def _update():
        project_path = Path(path).resolve()
        ctx = ContextManager(project_path)
        
        if not ctx.is_initialized:
            console.print(f"[yellow]Project not initialized. Run 'hive init' first.[/yellow]")
            raise typer.Exit(1)
        
        await ctx.load()
        
        updates = {}
        if architecture_notes:
            updates["architecture_notes"] = architecture_notes
        
        if add_important_file:
            current = ctx.config.important_files if ctx.config else []
            if add_important_file not in current:
                updates["important_files"] = current + [add_important_file]
        
        if updates:
            await ctx.update(**updates)
            console.print(f"[green]✓ Context updated![/green]")
        else:
            console.print("[yellow]No updates specified.[/yellow]")
    
    asyncio.run(_update())


@app.command()
def index(
    path: str = typer.Option(".", help="Path to codebase to index"),
    full: bool = typer.Option(False, "--full", "-f", help="Force full re-index"),
    status_only: bool = typer.Option(False, "--status", "-s", help="Show index status only"),
):
    """Index codebase for semantic search (RAG)."""
    from tools.rag import CodebaseIndexer, EmbeddingService, VectorDB
    
    async def _index():
        project_path = Path(path).resolve()
        
        # For status-only, don't need embedding service
        if status_only:
            vectordb = VectorDB(persist_dir=str(project_path / ".hive" / "vectordb"))
            indexer = CodebaseIndexer(
                workspace_path=str(project_path),
                vectordb=vectordb,
            )
            status = indexer.get_status()
            console.print("\n[bold blue]RAG Index Status[/bold blue]")
            console.print(f"  Workspace: {status['workspace_path']}")
            console.print(f"  Last indexed: {status['last_indexed'] or 'Never'}")
            console.print(f"  Indexed files: {status['indexed_files']}")
            console.print(f"  Total chunks: {status['total_chunks']}")
            return
        
        # Initialize components for indexing
        embedding_service = EmbeddingService()
        vectordb = VectorDB(persist_dir=str(project_path / ".hive" / "vectordb"))
        indexer = CodebaseIndexer(
            workspace_path=str(project_path),
            embedding_service=embedding_service,
            vectordb=vectordb,
        )
        
        console.print(f"\n[bold blue]Indexing codebase: {project_path}[/bold blue]")
        
        def progress(file_path: str, current: int, total: int):
            console.print(f"  [{current}/{total}] {Path(file_path).name}")
        
        if full:
            console.print("[yellow]Full re-index requested...[/yellow]")
            result = await indexer.index_full(progress_callback=progress)
        else:
            result = await indexer.index_changed_files(progress_callback=progress)
        
        console.print(f"\n[green]✓ Indexing complete![/green]")
        if full:
            console.print(f"  Files indexed: {result['files_indexed']}")
        else:
            console.print(f"  Files changed: {result['files_changed']}")
            console.print(f"  Files deleted: {result['files_deleted']}")
        console.print(f"  Chunks created: {result['chunks_created']}")
    
    asyncio.run(_index())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    path: str = typer.Option(".", help="Path to indexed codebase"),
    n_results: int = typer.Option(5, "-n", help="Number of results"),
):
    """Search indexed codebase semantically."""
    from tools.rag import RAGSearchTool
    
    async def _search():
        project_path = Path(path).resolve()
        
        tool = RAGSearchTool(workspace_path=str(project_path))
        result = await tool.execute(query=query, n_results=n_results)
        
        if result.success:
            console.print(f"\n[bold blue]Search Results for:[/bold blue] {query}\n")
            console.print(result.output)
        else:
            console.print(f"[red]Search failed: {result.error}[/red]")
    
    asyncio.run(_search())


@app.command()
def audit(
    path: str = typer.Option(".", help="Path to project"),
    tail: int = typer.Option(20, "-n", "--tail", help="Number of entries to show"),
    all_entries: bool = typer.Option(False, "--all", "-a", help="Show all entries"),
):
    """Show audit log of file operations."""
    from tools.guardrails import AuditLogger
    
    project_path = Path(path).resolve()
    log_file = project_path / ".hive" / "audit.log"
    
    if not log_file.exists():
        console.print("[yellow]No audit log found. No operations have been logged yet.[/yellow]")
        return
    
    logger = AuditLogger(workspace_path=str(project_path))
    
    if all_entries:
        with open(log_file) as f:
            entries = f.readlines()
    else:
        entries = logger.get_recent(tail)
    
    if not entries:
        console.print("[yellow]Audit log is empty.[/yellow]")
        return
    
    console.print(f"\n[bold blue]Audit Log[/bold blue] ({len(entries)} entries)\n")
    
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        
        # Color-code by result
        if "[blocked]" in entry:
            console.print(f"[red]{entry}[/red]")
        elif "[error]" in entry:
            console.print(f"[yellow]{entry}[/yellow]")
        elif "[success]" in entry:
            console.print(f"[green]{entry}[/green]")
        else:
            console.print(entry)


if __name__ == "__main__":
    app()
