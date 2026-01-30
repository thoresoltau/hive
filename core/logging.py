"""Human-readable logging for Hive Agent Swarm."""

import logging
import sys
from datetime import datetime
from typing import Optional
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.logging import RichHandler

from .activity_logger import get_activity_logger


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    AGENT = "agent"
    TOOL = "tool"
    WORKFLOW = "workflow"
    ERROR = "error"


# Rich console for pretty output
console = Console()

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_time=False, show_path=False)],
)

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


class HiveLogger:
    """Human-readable logger for Hive operations."""
    
    def __init__(self, verbose: bool = True, workspace_path: Optional[str] = None):
        self.verbose = verbose
        self.indent_level = 0
        self._current_cycle = 0
        self._current_agent = None
        self._workspace_path = workspace_path
        self._activity = None  # Lazy init
    
    def _get_activity(self):
        """Lazy-load activity logger."""
        if self._activity is None:
            self._activity = get_activity_logger(self._workspace_path)
        return self._activity
    
    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")
    
    def _indent(self) -> str:
        return "  " * self.indent_level
    
    # ─── Workflow Events ───
    
    def workflow_start(self, project: str, agents: list[str], tools_count: int):
        """Log workflow initialization."""
        self._get_activity().workflow_start(project, agents, tools_count)
        console.print()
        console.print(Panel.fit(
            f"[bold blue]🐝 Hive Agent Swarm[/bold blue]\n"
            f"[dim]Projekt:[/dim] {project}\n"
            f"[dim]Agents:[/dim] {', '.join(agents)}\n"
            f"[dim]Tools:[/dim] {tools_count}",
            title="Initialisierung",
            border_style="blue",
        ))
    
    def workflow_cycle_start(self, cycle: int, max_cycles: int):
        """Log start of a new workflow cycle."""
        self._current_cycle = cycle
        console.print()
        console.print(f"[bold cyan]━━━ Zyklus {cycle}/{max_cycles} ━━━[/bold cyan]")
    
    def workflow_cycle_end(self, result: Optional[str], message: Optional[str]):
        """Log end of a workflow cycle."""
        if result:
            status_icon = "✅" if "complete" in result.lower() or "success" in result.lower() else "📋"
            console.print(f"  [dim]{status_icon} {result}[/dim]")
        if message and self.verbose:
            # Truncate long messages
            msg = message[:150] + "..." if len(message) > 150 else message
            console.print(f"  [dim italic]→ {msg}[/dim italic]")
    
    def workflow_finish(self, summary: dict):
        """Log workflow completion."""
        console.print()
        
        table = Table(title="Sprint-Zusammenfassung", show_header=True, header_style="bold")
        table.add_column("Status", style="cyan")
        table.add_column("Anzahl", justify="right")
        
        status_icons = {
            "backlog": "📋",
            "refined": "📝",
            "planned": "📐",
            "in_progress": "🔨",
            "review": "👀",
            "done": "✅",
            "blocked": "🚫",
        }
        
        for status, count in summary.get("status_breakdown", {}).items():
            if count > 0:
                icon = status_icons.get(status, "•")
                table.add_row(f"{icon} {status}", str(count))
        
        console.print(table)
        console.print("\n[bold green]🏁 Workflow beendet[/bold green]")
    
    # ─── Agent Events ───
    
    def agent_start(self, agent_name: str, ticket_id: Optional[str] = None):
        """Log agent starting work."""
        self._get_activity().agent_start(agent_name, ticket_id)
        self._current_agent = agent_name
        agent_icons = {
            "scrum_master": "📊",
            "product_owner": "📋",
            "architect": "🏗️",
            "frontend_dev": "🎨",
            "backend_dev": "⚙️",
        }
        icon = agent_icons.get(agent_name, "🤖")
        ticket_info = f" [dim]({ticket_id})[/dim]" if ticket_id else ""
        console.print(f"\n{icon} [bold]{agent_name}[/bold]{ticket_info}")
        self.indent_level = 1
    
    def agent_thinking(self, task: str):
        """Log what the agent is doing."""
        if self.verbose:
            console.print(f"{self._indent()}[dim]💭 {task}[/dim]")
    
    def agent_decision(self, decision: str):
        """Log agent decision."""
        console.print(f"{self._indent()}[yellow]→ {decision}[/yellow]")
    
    def agent_handoff(self, from_agent: str, to_agent: str, reason: str = ""):
        """Log handoff between agents."""
        self._get_activity().agent_handoff(from_agent, to_agent, reason=reason)
        reason_text = f" [dim]({reason})[/dim]" if reason else ""
        console.print(f"{self._indent()}[blue]↗️ Übergabe an {to_agent}[/blue]{reason_text}")
    
    def agent_complete(self, action: str, success: bool, message: str = ""):
        """Log agent completion."""
        self._get_activity().agent_complete(self._current_agent or "unknown", action, success, message)
        self.indent_level = 0
        icon = "✅" if success else "⚠️"
        style = "green" if success else "yellow"
        console.print(f"  [{style}]{icon} {action}[/{style}]")
        if message and self.verbose:
            msg = message[:200] + "..." if len(message) > 200 else message
            console.print(f"  [dim]{msg}[/dim]")
    
    # ─── Tool Events ───
    
    def tool_call(self, tool_name: str, args: dict):
        """Log tool being called."""
        # Note: actual tool_call logging with success is done in tool_result
        if self.verbose:
            # Format args nicely
            args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(args.items())[:3])
            if len(args) > 3:
                args_str += ", ..."
            console.print(f"{self._indent()}[dim]🔧 {tool_name}({args_str})[/dim]")
    
    def tool_result(self, tool_name: str, success: bool, output_preview: str = ""):
        """Log tool result."""
        self._get_activity().tool_call(
            agent=self._current_agent or "unknown",
            tool=tool_name,
            args={},  # Args logged separately in tool_call
            success=success,
            error=output_preview if not success else None,
        )
        if self.verbose:
            icon = "✓" if success else "✗"
            style = "green" if success else "red"
            preview = f": {output_preview[:50]}..." if output_preview else ""
            console.print(f"{self._indent()}  [{style}]{icon}[/{style}]{preview}")
    
    def tool_retry(self, tool_name: str, attempt: int, max_attempts: int, error: str):
        """Log tool retry."""
        console.print(f"{self._indent()}[yellow]⟳ {tool_name} Versuch {attempt}/{max_attempts}: {error[:100]}[/yellow]")
    
    # ─── LLM Events ───
    
    def llm_call(self, purpose: str):
        """Log LLM being called."""
        if self.verbose:
            console.print(f"{self._indent()}[dim]🧠 LLM: {purpose}[/dim]")
    
    def llm_response(self, tokens_used: Optional[int] = None):
        """Log LLM response received."""
        if self.verbose and tokens_used:
            console.print(f"{self._indent()}  [dim]({tokens_used} tokens)[/dim]")
    
    # ─── Ticket Events ───
    
    def ticket_status_change(self, ticket_id: str, old_status: str, new_status: str):
        """Log ticket status change."""
        status_icons = {
            "backlog": "📋",
            "refined": "📝",
            "planned": "📐",
            "in_progress": "🔨",
            "review": "👀",
            "done": "✅",
            "blocked": "🚫",
        }
        old_icon = status_icons.get(old_status, "•")
        new_icon = status_icons.get(new_status, "•")
        console.print(f"{self._indent()}[cyan]{ticket_id}: {old_icon} {old_status} → {new_icon} {new_status}[/cyan]")
    
    def ticket_update(self, ticket_id: str, field: str, summary: str = ""):
        """Log ticket field update."""
        if self.verbose:
            console.print(f"{self._indent()}[dim]📝 {ticket_id}.{field} aktualisiert{': ' + summary if summary else ''}[/dim]")
    
    # ─── Error & Warning ───
    
    def error(self, message: str, exception: Optional[Exception] = None):
        """Log an error."""
        console.print(f"[bold red]❌ Fehler: {message}[/bold red]")
        if exception and self.verbose:
            console.print(f"[dim red]   {type(exception).__name__}: {exception}[/dim red]")
    
    def warning(self, message: str):
        """Log a warning."""
        console.print(f"[yellow]⚠️ {message}[/yellow]")
    
    def info(self, message: str):
        """Log info message."""
        console.print(f"[dim]{message}[/dim]")
    
    def debug(self, message: str):
        """Log debug message (only in verbose mode)."""
        if self.verbose:
            console.print(f"[dim]{self._indent()}• {message}[/dim]")


# Global logger instance
logger = HiveLogger(verbose=True)


def get_logger(verbose: bool = True) -> HiveLogger:
    """Get or create the global logger."""
    global logger
    logger.verbose = verbose
    return logger
