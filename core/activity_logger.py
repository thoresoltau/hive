"""Activity logging for tracking all agent and tool operations."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from threading import Lock


class ActivityLogger:
    """
    Logs all agent and tool activity to .hive/activity.jsonl.
    
    Provides a complete audit trail of:
    - Agent lifecycle (start, complete, handoff)
    - Tool calls with arguments and results
    - Ticket status changes
    - LLM calls
    - Workflow events
    """
    
    _instance: Optional["ActivityLogger"] = None
    _lock = Lock()
    
    def __new__(cls, workspace_path: Optional[str] = None):
        """Singleton pattern to ensure one logger per workspace."""
        with cls._lock:
            if cls._instance is None or workspace_path:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance
    
    def __init__(self, workspace_path: Optional[str] = None):
        if self._initialized and not workspace_path:
            return
            
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.log_file = self.workspace_path / ".hive" / "activity.jsonl"
        self.max_size_mb = 50
        self._ensure_log_dir()
        self._initialized = True
    
    def _ensure_log_dir(self) -> None:
        """Ensure log directory exists."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.log_file.exists():
            return
        
        max_bytes = self.max_size_mb * 1024 * 1024
        if self.log_file.stat().st_size > max_bytes:
            # Rotate: activity.jsonl -> activity.jsonl.1
            backup = self.log_file.with_suffix(".jsonl.1")
            if backup.exists():
                backup.unlink()
            self.log_file.rename(backup)
    
    def log(
        self,
        event_type: str,
        agent: Optional[str] = None,
        **data: Any,
    ) -> None:
        """
        Log an activity event.
        
        Args:
            event_type: Type of event (agent_start, tool_call, etc.)
            agent: Name of agent performing the action
            **data: Additional event-specific data
        """
        self._rotate_if_needed()
        
        event = {
            "ts": datetime.now().isoformat(),
            "type": event_type,
        }
        
        if agent:
            event["agent"] = agent
        
        event.update(data)
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass  # Don't crash on logging failures
    
    # Convenience methods for common event types
    
    def workflow_start(
        self,
        project: str,
        agents: list[str],
        tools_count: int,
    ) -> None:
        """Log workflow initialization."""
        self.log(
            "workflow_start",
            project=project,
            agents=agents,
            tools_count=tools_count,
        )
    
    def workflow_cycle(
        self,
        cycle: int,
        max_cycles: int,
        result: Optional[str] = None,
    ) -> None:
        """Log workflow cycle."""
        self.log(
            "workflow_cycle",
            cycle=cycle,
            max_cycles=max_cycles,
            result=result,
        )
    
    def agent_start(
        self,
        agent: str,
        ticket: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> None:
        """Log agent starting work."""
        self.log(
            "agent_start",
            agent=agent,
            ticket=ticket,
            task_type=task_type,
        )
    
    def agent_complete(
        self,
        agent: str,
        action: str,
        success: bool,
        message: str = "",
    ) -> None:
        """Log agent completing work."""
        self.log(
            "agent_complete",
            agent=agent,
            action=action,
            success=success,
            message=message[:200],  # Truncate long messages
        )
    
    def agent_handoff(
        self,
        from_agent: str,
        to_agent: str,
        ticket: Optional[str] = None,
        reason: str = "",
    ) -> None:
        """Log handoff between agents."""
        self.log(
            "agent_handoff",
            from_agent=from_agent,
            to_agent=to_agent,
            ticket=ticket,
            reason=reason[:100],
        )
    
    def tool_call(
        self,
        agent: str,
        tool: str,
        args: dict,
        success: bool,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Log tool invocation."""
        # Sanitize args - truncate large values
        safe_args = {}
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 100:
                safe_args[k] = v[:100] + "..."
            else:
                safe_args[k] = v
        
        self.log(
            "tool_call",
            agent=agent,
            tool=tool,
            args=safe_args,
            success=success,
            error=error[:200] if error else None,
            duration_ms=duration_ms,
        )
    
    def ticket_update(
        self,
        agent: str,
        ticket: str,
        field: str,
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        """Log ticket field change."""
        self.log(
            "ticket_update",
            agent=agent,
            ticket=ticket,
            field=field,
            old=str(old_value)[:50] if old_value else None,
            new=str(new_value)[:50] if new_value else None,
        )
    
    def llm_call(
        self,
        agent: str,
        purpose: str,
        tokens: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Log LLM API call."""
        self.log(
            "llm_call",
            agent=agent,
            purpose=purpose[:100],
            tokens=tokens,
            duration_ms=duration_ms,
        )
    
    def get_events(
        self,
        n: int = 50,
        event_type: Optional[str] = None,
        agent: Optional[str] = None,
        ticket: Optional[str] = None,
    ) -> list[dict]:
        """
        Get recent events with optional filtering.
        
        Args:
            n: Maximum number of events to return
            event_type: Filter by event type
            agent: Filter by agent name
            ticket: Filter by ticket ID
            
        Returns:
            List of event dictionaries (most recent last)
        """
        if not self.log_file.exists():
            return []
        
        events = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        
                        # Apply filters
                        if event_type and event.get("type") != event_type:
                            continue
                        if agent and event.get("agent") != agent:
                            continue
                        if ticket and event.get("ticket") != ticket:
                            continue
                        
                        events.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []
        
        return events[-n:]


# Global instance getter
_activity_logger: Optional[ActivityLogger] = None


def get_activity_logger(workspace_path: Optional[str] = None) -> ActivityLogger:
    """Get or create the activity logger singleton."""
    global _activity_logger
    if _activity_logger is None or workspace_path:
        _activity_logger = ActivityLogger(workspace_path)
    return _activity_logger
