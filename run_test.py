#!/usr/bin/env python3
"""
Test-Lauf der Hive Agents für test-hive-project.
"""

import asyncio
import os
from pathlib import Path
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()

console = Console()

# Paths
HIVE_DIR = Path(__file__).parent
TEST_PROJECT = Path.home() / "test-hive-project"
CONFIG_PATH = HIVE_DIR / "config" / "agents.yaml"


async def run_test():
    """Run agents on test-hive-project."""
    from core.orchestrator import Orchestrator
    
    console.print("\n[bold blue]🐝 Hive Agent Swarm - Test Run[/bold blue]")
    console.print(f"   Project: {TEST_PROJECT}")
    console.print(f"   Backlog: {TEST_PROJECT / 'backlog'}")
    console.print()
    
    # Create orchestrator with test project paths
    orchestrator = Orchestrator(
        backlog_path=TEST_PROJECT / "backlog",
        config_path=CONFIG_PATH,
        codebase_path=TEST_PROJECT,
    )
    
    await orchestrator.initialize()
    
    # Show current backlog status
    console.print("\n[bold]Current Backlog:[/bold]")
    tickets = orchestrator.backlog.get_all_tickets()
    for ticket in tickets:
        console.print(f"  • {ticket.id}: {ticket.title} [{ticket.status.value}]")
    
    if not tickets:
        console.print("  [yellow]No tickets found![/yellow]")
        return
    
    # Ask for confirmation before running
    console.print("\n[bold yellow]⚠️  This will use the OpenAI API and modify files![/bold yellow]")
    response = input("Continue? [y/N]: ")
    
    if response.lower() != 'y':
        console.print("[red]Aborted.[/red]")
        return
    
    # Process first ticket (HIVE-001)
    console.print("\n[bold green]Starting Agent Workflow...[/bold green]\n")
    
    try:
        # Run one cycle to process the first ticket
        result = await orchestrator.run(max_cycles=3)
        console.print(f"\n[green]✅ Run completed![/green]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


if __name__ == "__main__":
    asyncio.run(run_test())
