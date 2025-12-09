"""Backlog manager for ticket operations."""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import yaml
import aiofiles

from .models import Ticket, TicketStatus, Priority


class BacklogManager:
    """Manages ticket lifecycle and persistence."""

    def __init__(self, backlog_path: str | Path):
        self.backlog_path = Path(backlog_path)
        self.tickets_dir = self.backlog_path / "tickets"
        self.index_file = self.backlog_path / "index.yaml"
        self._tickets: dict[str, Ticket] = {}
        self._index: dict = {}

    async def initialize(self) -> None:
        """Initialize backlog directory structure."""
        self.tickets_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.index_file.exists():
            self._index = {
                "project": "Hive Agent Swarm",
                "current_sprint": 1,
                "tickets": [],
                "sprint_backlog": [],
            }
            await self._save_index()
        else:
            await self._load_index()
            await self._load_all_tickets()

    async def _save_index(self) -> None:
        """Save index file."""
        async with aiofiles.open(self.index_file, "w") as f:
            await f.write(yaml.dump(self._index, default_flow_style=False, allow_unicode=True))

    async def _load_index(self) -> None:
        """Load index file."""
        async with aiofiles.open(self.index_file, "r") as f:
            content = await f.read()
            self._index = yaml.safe_load(content) or {}

    async def _load_all_tickets(self) -> None:
        """Load all tickets from disk."""
        for ticket_info in self._index.get("tickets", []):
            ticket_file = self.backlog_path / ticket_info["file"]
            if ticket_file.exists():
                ticket = await self.load_ticket_from_file(ticket_file)
                if ticket:
                    self._tickets[ticket.id] = ticket

    async def load_ticket_from_file(self, file_path: Path) -> Optional[Ticket]:
        """Load a single ticket from file."""
        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                data = yaml.safe_load(content)
                return Ticket.model_validate(data)
        except Exception as e:
            print(f"Error loading ticket from {file_path}: {e}")
            return None

    async def save_ticket(self, ticket: Ticket) -> None:
        """Save a ticket to disk and update index."""
        ticket.metadata.updated_at = datetime.utcnow()
        
        # Save ticket file
        ticket_file = self.tickets_dir / f"{ticket.id}.yaml"
        ticket_data = ticket.model_dump(mode="json")
        
        # Convert datetime objects to strings for YAML
        async with aiofiles.open(ticket_file, "w") as f:
            await f.write(yaml.dump(ticket_data, default_flow_style=False, allow_unicode=True))
        
        # Update in-memory cache
        self._tickets[ticket.id] = ticket
        
        # Update index
        relative_path = f"tickets/{ticket.id}.yaml"
        ticket_entry = {
            "id": ticket.id,
            "file": relative_path,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
        }
        
        # Update or add to index
        existing_idx = next(
            (i for i, t in enumerate(self._index["tickets"]) if t["id"] == ticket.id),
            None
        )
        if existing_idx is not None:
            self._index["tickets"][existing_idx] = ticket_entry
        else:
            self._index["tickets"].append(ticket_entry)
        
        await self._save_index()

    async def create_ticket(
        self,
        id: str,
        title: str,
        description: str,
        type: str = "feature",
        priority: str = "medium",
    ) -> Ticket:
        """Create a new ticket."""
        from .models import TicketType
        
        ticket = Ticket(
            id=id,
            type=TicketType(type),
            title=title,
            description=description,
            priority=Priority(priority),
        )
        await self.save_ticket(ticket)
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def get_all_tickets(self) -> list[Ticket]:
        """Get all tickets."""
        return list(self._tickets.values())

    def get_tickets_by_status(self, status: TicketStatus) -> list[Ticket]:
        """Get tickets filtered by status."""
        return [t for t in self._tickets.values() if t.status == status]

    def get_next_ticket_for_refinement(self) -> Optional[Ticket]:
        """Get the next ticket that needs refinement."""
        backlog_tickets = self.get_tickets_by_status(TicketStatus.BACKLOG)
        if not backlog_tickets:
            return None
        
        # Sort by priority
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        backlog_tickets.sort(key=lambda t: priority_order[t.priority])
        return backlog_tickets[0]

    def get_next_ticket_for_work(self) -> Optional[Ticket]:
        """Get the next ticket ready for implementation."""
        planned_tickets = self.get_tickets_by_status(TicketStatus.PLANNED)
        ready_tickets = [t for t in planned_tickets if t.can_start()]
        
        if not ready_tickets:
            return None
        
        # Sort by priority
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        ready_tickets.sort(key=lambda t: priority_order[t.priority])
        return ready_tickets[0]

    async def update_ticket_status(self, ticket_id: str, new_status: TicketStatus) -> Optional[Ticket]:
        """Update a ticket's status."""
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket.status = new_status
            await self.save_ticket(ticket)
        return ticket

    def get_sprint_summary(self) -> dict:
        """Get summary of current sprint."""
        sprint_tickets = [
            t for t in self._tickets.values()
            if t.metadata.sprint == self._index.get("current_sprint")
        ]
        
        status_counts = {}
        for status in TicketStatus:
            status_counts[status.value] = len([
                t for t in sprint_tickets if t.status == status
            ])
        
        return {
            "sprint": self._index.get("current_sprint"),
            "total_tickets": len(sprint_tickets),
            "status_breakdown": status_counts,
        }
