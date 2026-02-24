#!/usr/bin/env python3
"""
Hive - A digital swarm, autonomously developing your project.

Usage:
    hive infest                # Settle the swarm in the current directory
    hive hatch                 # Hatch a new ticket
    hive swarm                 # Unleash the swarm
    hive swarm TICKET-ID      # Direct the swarm to a specific target (ticket)
    hive pulse                 # Feel the pulse of the swarm (backlog status)
"""

import asyncio
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.overmind import Overmind
    from core.hatchery import Hatchery
    from core.context import ContextManager

from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

app = typer.Typer(help="Hive - A digital swarm, autonomously developing your project.")
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
        "No Hive project found. Run 'hive infest'."
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

def get_overmind() -> "Overmind":
    """Create orchestrator instance for current project."""
    from core.overmind import Overmind

    project_path = get_project_path()
    return Overmind(
        hatchery_path=get_tickets_dir().parent,  # .hive/
        config_path=get_config_path(),
        codebase_path=str(project_path),
    )


def get_hatchery() -> "Hatchery":
    """Get backlog manager for current project."""
    from core.hatchery import Hatchery
    return Hatchery(get_hive_dir())


def get_context_manager() -> "ContextManager":
    """Get context manager for current project."""
    from core.context import ContextManager
    return ContextManager(get_project_path())


# === Commands ===

@app.command(name="infest")
def infest(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
):
    """
    Initializes the current directory for the Hive.

    Creates .hive/ with project configuration.
    """
    from core.context import ContextManager

    project_path = Path.cwd()
    hive_dir = project_path / ".hive"

    if hive_dir.exists() and not force:
        console.print(f"[yellow]⚠ Hive already initialized in {project_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    # Get project info interactively
    project_name = project_path.name
    project_name = Prompt.ask("Project name", default=project_name)
    description = Prompt.ask("Description", default="")

    # Get tech stack
    console.print("\n[bold]Tech Stack[/bold] (comma-separated, empty for auto-detect)")
    languages = Prompt.ask("Languages", default="")
    frameworks = Prompt.ask("Frameworks", default="")

    tech_stack = {}
    if languages:
        tech_stack["languages"] = [lang.strip() for lang in languages.split(",")]
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

        console.print("\n[green]✓ Directory infested! The Hive is growing.[/green]")
        console.print(f"  Project: {project_path}")
        console.print(f"  Config: {hive_dir / 'project.yaml'}")
        console.print(f"  Tickets: {tickets_dir}")

        if config.tech_stack.languages:
            console.print("\n[bold]Detected:[/bold]")
            console.print(f"  Languages: {', '.join(config.tech_stack.languages)}")

    asyncio.run(_init())


@app.command(name="init", hidden=True)
def init_alias(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
):
    """Alias for infest."""
    infest(force=force)


@app.command(name="swarm")
@require_initialized
def swarm(
    ticket_id: Optional[str] = typer.Argument(None, help="Optional Ticket ID (e.g. HIVE-001)"),
    max_cycles: int = typer.Option(20, "--max-cycles", "-n", help="Maximum mutation cycles"),
):
    """Starts the swarm (processes Hatchery backlog or a specific ticket)."""
    async def _run():
        orchestrator = get_overmind()
        await orchestrator.initialize()
        if ticket_id:
            response = await orchestrator.process_ticket(ticket_id)
            console.print(f"\n[bold]Result:[/bold] {response.action_taken}")
            console.print(f"[bold]Message:[/bold] {response.message}")
        else:
            await orchestrator.run(max_cycles=max_cycles)

    project = get_project_path()
    if ticket_id:
        console.print(f"[blue]🦑 Swarm is evolving (Ticket {ticket_id}) on {project}[/blue]\n")
    else:
        console.print(f"[blue]🦑 Swarm is spawning on {project}[/blue]\n")
    asyncio.run(_run())


@app.command(name="run", hidden=True)
@require_initialized
def run(max_cycles: int = typer.Option(20, "--max-cycles", "-n", help="Maximum cycles")):
    """Alias for swarm."""
    swarm(ticket_id=None, max_cycles=max_cycles)


@app.command(name="process", hidden=True)
@require_initialized
def process(
    ticket_id: str = typer.Argument(..., help="Ticket ID"),
    max_cycles: int = typer.Option(20, "--max-cycles", "-n", help="Maximum cycles"),
):
    """Alias for swarm <ticket_id>."""
    swarm(ticket_id=ticket_id, max_cycles=max_cycles)


@app.command(name="hibernate")
@require_initialized
def hibernate():
    """Puts the swarm into hibernation (Stop)."""
    console.print("[blue]💤 The Overmind is sleeping. Swarm is hibernating.[/blue]")


@app.command(name="stop", hidden=True)
@require_initialized
def stop():
    """Alias for hibernate."""
    hibernate()


@app.command("hatch")
@require_initialized
def hatch():
    """Hatches a new ticket interactively."""

    console.print("\n[bold blue]Hatch a new ticket[/bold blue]\n")

    # Auto-generate ticket ID
    tickets_dir = get_tickets_dir()
    existing = list(tickets_dir.glob("*.yaml"))
    next_num = len(existing) + 1

    # Get project prefix from config
    try:
        get_context_manager()
        prefix = "HIVE"  # TODO: Get from project config
    except Exception:
        prefix = "HIVE"

    default_id = f"{prefix}-{next_num:03d}"

    ticket_id = Prompt.ask("Ticket ID", default=default_id)
    title = Prompt.ask("Title")

    console.print("\nTypes: feature, bug, refactor, chore, spike")
    ticket_type = Prompt.ask("Type", default="feature")

    console.print("\nPriorities: critical, high, medium, low")
    priority = Prompt.ask("Priority", default="medium")

    console.print("\nDescription (empty line to end):")
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

    console.print(f"\n[green]✅ Ticket {ticket_id} created![/green]")
    console.print(f"   File: {ticket_file}")


@app.command(name="pulse")
@require_initialized
def pulse():
    """Shows the status of the hatchery."""
    tickets_dir = get_tickets_dir()

    if not tickets_dir.exists():
        console.print("[yellow]No tickets available.[/yellow]")
        return

    ticket_files = list(tickets_dir.glob("*.yaml"))

    if not ticket_files:
        console.print("[yellow]No tickets in hatchery.[/yellow]")
        return

    import yaml

    table = Table(title=f"Backlog ({get_project_path().name})")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")

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


@app.command(name="status", hidden=True)
@require_initialized
def status_alias():
    """Alias for pulse."""
    pulse()


@app.command(name="dissect")
@require_initialized
def dissect(ticket_id: str = typer.Argument(..., help="Ticket ID to dissect")):
    """Dissects a ticket (shows detailed information)."""
    import yaml

    ticket_file = get_tickets_dir() / f"{ticket_id}.yaml"

    if not ticket_file.exists():
        console.print(f"[red]Ticket {ticket_id} not found.[/red]")
        raise typer.Exit(1)

    with open(ticket_file) as f:
        ticket = yaml.safe_load(f)

    console.print(f"\n[bold cyan]Ticket: {ticket.get('id')}[/bold cyan]")
    console.print(f"[bold]Title:[/bold] {ticket.get('title')}")
    console.print(f"[bold]Type:[/bold] {ticket.get('type')}")
    console.print(f"[bold]Status:[/bold] {ticket.get('status')}")
    console.print(f"[bold]Priority:[/bold] {ticket.get('priority')}")
    console.print(f"\n[bold]Description:[/bold]\n{ticket.get('description', '')}")


@app.command(name="assimilate")
@require_initialized
def assimilate(
    full: bool = typer.Option(False, "--full", "-f", help="Force full assimilation"),
    status_only: bool = typer.Option(False, "--status", "-s", help="Show only the assimilation status"),
):
    """Assimilates (indexes) the codebase into the swarm (RAG)."""
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
            console.print("\n[bold blue]Thought assimilation status[/bold blue]")
            console.print(f"  Project: {status['workspace_path']}")
            console.print(f"  Last assimilation: {status['last_indexed'] or 'Never'}")
            console.print(f"  Assimilated files: {status['indexed_files']}")
            console.print(f"  Chunks: {status['total_chunks']}")
            return

        embedding_service = EmbeddingService()
        vectordb = VectorDB(persist_dir=str(hive_dir / "vectordb"))
        indexer = CodebaseIndexer(
            workspace_path=str(project_path),
            embedding_service=embedding_service,
            vectordb=vectordb,
        )

        console.print(f"\n[bold blue]Assimilating knowledge: {project_path}[/bold blue]")

        def progress(file_path: str, current: int, total: int):
            console.print(f"  [{current}/{total}] {Path(file_path).name}")

        if full:
            console.print("[yellow]Full assimilation of the codebase...[/yellow]")
            result = await indexer.index_full(progress_callback=progress)
        else:
            result = await indexer.index_changed_files(progress_callback=progress)

        console.print("\n[green]✓ Assimilation into the swarm completed![/green]")
        if full:
            console.print(f"  Files: {result['files_indexed']}")
        else:
            console.print(f"  Changed: {result['files_changed']}")
            console.print(f"  Deleted: {result['files_deleted']}")
        console.print(f"  Chunks: {result['chunks_created']}")

    asyncio.run(_index())


@app.command(name="index", hidden=True)
@require_initialized
def index(
    full: bool = typer.Option(False, "--full", "-f"),
    status_only: bool = typer.Option(False, "--status", "-s"),
):
    """Alias for assimilate."""
    assimilate(full=full, status_only=status_only)


@app.command(name="scout")
@require_initialized
def scout(
    query: str = typer.Argument(..., help="Scouting mission (search query)"),
    n_results: int = typer.Option(5, "-n", help="Number of results"),
):
    """Sends a scout to semantically search the codebase."""
    from tools.rag import RAGSearchTool

    project_path = get_project_path()

    async def _search():
        tool = RAGSearchTool(workspace_path=str(project_path))
        result = await tool.execute(query=query, n_results=n_results)

        if result.success:
            console.print(f"\n[bold blue]Search:[/bold blue] {query}\n")
            console.print(result.output)
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    asyncio.run(_search())


@app.command(name="trails")
@require_initialized
def trails(
    tail: int = typer.Option(20, "-n", "--tail", help="Number of trails"),
    all_entries: bool = typer.Option(False, "--all", "-a", help="Show all trails"),
):
    """Shows the trails of file operations."""
    from tools.guardrails import AuditLogger

    project_path = get_project_path()
    log_file = get_hive_dir() / "audit.log"

    if not log_file.exists():
        console.print("[yellow]No trails available.[/yellow]")
        return

    logger = AuditLogger(workspace_path=str(project_path))

    if all_entries:
        with open(log_file) as f:
            entries = f.readlines()
    else:
        entries = logger.get_recent(tail)

    if not entries:
        console.print("[yellow]No trails found.[/yellow]")
        return

    console.print(f"\n[bold blue]Trails (Audit Log)[/bold blue] ({len(entries)} entries)\n")

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


@app.command(name="refresh")
@app.command(name="update", hidden=True)
@require_initialized
def refresh():
    """Safely regenerate context config and detect new frameworks."""
    import asyncio
    from core.context import ContextManager

    project_dir = get_project_path()

    async def _run():
        ctx = ContextManager(project_dir)
        try:
            config = await ctx.refresh()
            if config:
                console.print(f"[green]✓ Swarm context refreshed successfully![/green]")
                console.print(f"[dim]Detected Tech Stack:[/dim] {', '.join(config.tech_stack.languages) if config.tech_stack.languages else 'None'}")
            else:
                console.print("[red]✗ Failed to load or refresh config.[/red]")
        except Exception as e:
            console.print(f"[red]Error during refresh: {e}[/red]")

    console.print(f"[blue]🔄 Refreshing swarm configuration on {project_dir}...[/blue]")
    asyncio.run(_run())


@app.command(name="observe")
@require_initialized
def observe(
    tail: int = typer.Option(50, "-n", "--tail", help="Number of events"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Filter by strain/agent"),
    ticket: Optional[str] = typer.Option(None, "--ticket", "-t", help="Filter by larva/ticket"),
    event_type: Optional[str] = typer.Option(None, "--type", help="Filter by event type"),
):
    """Observes the swarm at work."""
    from core.overseer import Overseer

    project_path = get_project_path()
    logger = Overseer(workspace_path=str(project_path))

    events = logger.get_events(
        n=tail,
        event_type=event_type,
        agent=agent,
        ticket=ticket,
    )

    if not events:
        console.print("[yellow]No swarm activities observed.[/yellow]")
        if agent or ticket or event_type:
            console.print(f"[dim]Filter: agent={agent}, ticket={ticket}, type={event_type}[/dim]")
        return

    console.print(f"\n[bold blue]Swarm Network (Activity Log)[/bold blue] ({len(events)} Events)\n")

    # Event type icons
    icons = {
        "workflow_start": "🚀",
        "workflow_cycle": "🔄",
        "agent_start": "🤖",
        "agent_complete": "✅",
        "agent_handoff": "🔀",
        "tool_call": "🧬",
        "ticket_update": "📝",
        "llm_call": "🧠",
    }

    from core.logging import HiveLogger

    for event in events:
        ts = event.get("ts", "")[:19].replace("T", " ")
        etype = event.get("type", "unknown")
        icon = icons.get(etype, "•")

        raw_agent_name = event.get("agent", event.get("from_agent", ""))
        agent_name = HiveLogger.AGENT_NAMES.get(raw_agent_name, raw_agent_name.upper()) if raw_agent_name else "SYSTEM"

        # Format based on event type
        if etype == "tool_call":
            tool = event.get("tool", "?")
            success = "✓" if event.get("success") else "✗"
            style = "green" if event.get("success") else "red"
            console.print(f"[dim]{ts}[/dim] {icon} [{style}]{success}[/{style}] [cyan]{agent_name}[/cyan] → {tool}")
        elif etype == "agent_handoff":
            raw_to_agent = event.get("to_agent", "?")
            to_agent = HiveLogger.AGENT_NAMES.get(raw_to_agent, raw_to_agent.upper())
            console.print(f"[dim]{ts}[/dim] {icon} [cyan]{agent_name}[/cyan] → [cyan]{to_agent}[/cyan]")
        elif etype == "ticket_update":
            ticket_id = event.get("ticket", "?")
            field = event.get("field", "?")
            new_val = event.get("new", "?")
            console.print(f"[dim]{ts}[/dim] {icon} [cyan]{agent_name}[/cyan] {ticket_id}.{field} = {new_val}")
        else:
            msg = event.get("action", event.get("message", etype))
            console.print(f"[dim]{ts}[/dim] {icon} [cyan]{agent_name}[/cyan] {msg}")


@app.command(name="essence")
@require_initialized
def essence():
    """Shows the essence provided to the agents."""
    async def _context():
        ctx = get_context_manager()
        full_context = await ctx.get_full_context()
        console.print(full_context)

    asyncio.run(_context())


if __name__ == "__main__":
    app()
