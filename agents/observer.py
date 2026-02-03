
from datetime import datetime, timedelta
from typing import Any, Optional
from collections import deque

from core.models import AgentMessage, AgentResponse, MessageType
from .base_agent import BaseAgent

class ObserverAgent(BaseAgent):
    """
    Passive observer agent that monitors swarm health.
    Detects error spikes, stagnant workflows, and circular dependencies.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Tracking metrics
        self._error_window = deque(maxlen=50) # Store timestamps of errors
        self._last_progress = datetime.utcnow()
        self._message_count = 0
        
        # Thresholds
        self.ERROR_THRESHOLD_PER_MIN = 5
        self.STAGNATION_TIMEOUT_SEC = 300 # 5 minutes
        
    async def initialize(self) -> None:
        """Initialize and subscribe to global stream."""
        # Subscribe to EVERYTHING
        self.message_bus.subscribe_to_all(self._monitor_callback)
        self.log.info("Observer online and monitoring global stream.")

    async def _monitor_callback(self, message: AgentMessage) -> None:
        """Callback for every message in the system."""
        self._message_count += 1
        
        # 1. Error Detection
        if "error" in message.content.lower() or "exception" in message.content.lower() or "fail" in message.content.lower():
            # Filter out expected errors if needed? For now, count all noise.
            # Maybe check if it's a ToolResult failure?
            if "CRITICAL_FAILURE" in message.content:
                 self._record_error()
        
        # 2. Progress Detection
        if message.message_type in [MessageType.RESPONSE, MessageType.HANDOFF]:
            # Reset progress timer if meaningful work happened
            if "ticket_already_done" not in message.content:
                self._last_progress = datetime.utcnow()

        # 3. Check for anomalies
        await self._check_health()

    def _record_error(self) -> None:
        now = datetime.utcnow()
        self._error_window.append(now)
        
        # Cleanup old errors (> 1 min)
        while self._error_window and (now - self._error_window[0]).total_seconds() > 60:
            self._error_window.popleft()
            
        if len(self._error_window) >= self.ERROR_THRESHOLD_PER_MIN:
            # We are in a storm!
            # Avoid spamming alerts?
            pass

    async def _check_health(self) -> None:
        """Periodic health check logic."""
        now = datetime.utcnow()
        
        # Check Error Rate
        # Clean window first
        while self._error_window and (now - self._error_window[0]).total_seconds() > 60:
            self._error_window.popleft()
            
        rate = len(self._error_window)
        if rate >= self.ERROR_THRESHOLD_PER_MIN:
            await self._alert(f"🚨 HIGH ERROR RATE DETECTED: {rate} errors in last minute!")
            self._error_window.clear() # Reset to avoid spam

        # Check Stagnation
        if (now - self._last_progress).total_seconds() > self.STAGNATION_TIMEOUT_SEC:
             # Only alert if we ARE running (how to know? message count moving?)
             pass

    async def _alert(self, warning: str) -> None:
        """Broadcast an alert."""
        self.log.warning(f"OBSERVER ALERT: {warning}")
        
        # Send to Orchestrator or Broadcast?
        await self.message_bus.broadcast(
            from_agent=self.name,
            content=warning,
            message_type=MessageType.UPDATE 
        )

    async def process_task(self, ticket_id: str, context: dict) -> dict:
        """Observer usually doesn't process tickets directly."""
        return {"status": "observing"}
