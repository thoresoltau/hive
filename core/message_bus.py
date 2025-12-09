"""Message bus for inter-agent communication."""

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Callable, Optional, Any
from dataclasses import dataclass, field

from .models import AgentMessage, MessageType


@dataclass
class MessageSubscription:
    """Subscription to message bus."""
    agent_name: str
    callback: Callable[[AgentMessage], Any]
    message_types: list[MessageType] = field(default_factory=list)


class MessageBus:
    """
    Central message bus for agent communication.
    
    Supports:
    - Direct messaging between agents
    - Broadcast messages
    - Message history for context
    - Async message handling
    """

    def __init__(self, history_limit: int = 100):
        self._subscriptions: dict[str, MessageSubscription] = {}
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._history: list[AgentMessage] = []
        self._history_limit = history_limit
        self._running = False
        self._handlers: dict[str, Callable] = {}

    def subscribe(
        self,
        agent_name: str,
        callback: Callable[[AgentMessage], Any],
        message_types: Optional[list[MessageType]] = None,
    ) -> None:
        """Subscribe an agent to receive messages."""
        self._subscriptions[agent_name] = MessageSubscription(
            agent_name=agent_name,
            callback=callback,
            message_types=message_types or [],
        )
        self._handlers[agent_name] = callback

    def unsubscribe(self, agent_name: str) -> None:
        """Unsubscribe an agent from messages."""
        self._subscriptions.pop(agent_name, None)
        self._handlers.pop(agent_name, None)

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to the bus."""
        # Add to history
        self._history.append(message)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]
        
        # Queue for processing
        await self._message_queue.put(message)

    async def send_direct(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        message_type: MessageType = MessageType.TASK,
        ticket_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> Optional[Any]:
        """Send a direct message to a specific agent and wait for response."""
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            ticket_id=ticket_id,
            content=content,
            context=context or {},
        )
        
        # Add to history
        self._history.append(message)
        
        # Direct delivery if handler exists
        if to_agent in self._handlers:
            handler = self._handlers[to_agent]
            return await handler(message)
        
        return None

    async def broadcast(
        self,
        from_agent: str,
        content: str,
        message_type: MessageType = MessageType.UPDATE,
        ticket_id: Optional[str] = None,
        exclude: Optional[list[str]] = None,
    ) -> None:
        """Broadcast a message to all subscribed agents."""
        exclude = exclude or []
        
        for agent_name in self._subscriptions:
            if agent_name != from_agent and agent_name not in exclude:
                message = AgentMessage(
                    from_agent=from_agent,
                    to_agent=agent_name,
                    message_type=message_type,
                    ticket_id=ticket_id,
                    content=content,
                )
                await self._message_queue.put(message)

    def get_history(
        self,
        ticket_id: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int = 50,
    ) -> list[AgentMessage]:
        """Get message history with optional filters."""
        messages = self._history
        
        if ticket_id:
            messages = [m for m in messages if m.ticket_id == ticket_id]
        
        if agent:
            messages = [
                m for m in messages
                if m.from_agent == agent or m.to_agent == agent
            ]
        
        return messages[-limit:]

    def get_conversation_context(self, ticket_id: str, limit: int = 10) -> str:
        """Get formatted conversation context for a ticket."""
        messages = self.get_history(ticket_id=ticket_id, limit=limit)
        
        if not messages:
            return "Keine vorherigen Nachrichten zu diesem Ticket."
        
        context_parts = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%H:%M")
            context_parts.append(
                f"[{timestamp}] {msg.from_agent} -> {msg.to_agent}: {msg.content[:200]}"
            )
        
        return "\n".join(context_parts)

    async def start(self) -> None:
        """Start the message bus processing loop."""
        self._running = True
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                await self._process_message(message)
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False

    async def _process_message(self, message: AgentMessage) -> None:
        """Process a single message."""
        subscription = self._subscriptions.get(message.to_agent)
        
        if subscription:
            # Check message type filter
            if (
                not subscription.message_types
                or message.message_type in subscription.message_types
            ):
                try:
                    await subscription.callback(message)
                except Exception as e:
                    print(f"Error processing message for {message.to_agent}: {e}")

    def clear_history(self) -> None:
        """Clear message history."""
        self._history = []
