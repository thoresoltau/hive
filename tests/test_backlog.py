"""Tests for backlog management."""

import pytest
from pathlib import Path

from core.backlog import BacklogManager
from core.models import TicketStatus, TicketType, Priority


class TestBacklogManager:
    """Tests for BacklogManager."""

    @pytest.fixture
    def backlog_dir(self, temp_dir):
        """Create backlog directory structure."""
        backlog = temp_dir / "backlog"
        backlog.mkdir()
        (backlog / "tickets").mkdir()
        return backlog

    @pytest.fixture
    def manager(self, backlog_dir):
        return BacklogManager(backlog_dir)

    async def test_initialize_creates_index(self, manager, backlog_dir):
        """Should create index.yaml on initialize."""
        await manager.initialize()
        
        assert (backlog_dir / "index.yaml").exists()

    async def test_create_ticket(self, manager):
        """Should create a new ticket."""
        await manager.initialize()
        
        ticket = await manager.create_ticket(
            id="TEST-001",
            title="Test Ticket",
            description="This is a test ticket.",
            type="feature",
            priority="medium",
        )
        
        assert ticket.id == "TEST-001"
        assert ticket.title == "Test Ticket"
        assert ticket.status == TicketStatus.BACKLOG

    async def test_get_ticket(self, manager):
        """Should retrieve ticket by ID."""
        await manager.initialize()
        await manager.create_ticket(
            id="TEST-001",
            title="Test Ticket",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        ticket = manager.get_ticket("TEST-001")
        
        assert ticket is not None
        assert ticket.id == "TEST-001"

    async def test_get_nonexistent_ticket(self, manager):
        """Should return None for non-existent ticket."""
        await manager.initialize()
        
        ticket = manager.get_ticket("NONEXISTENT")
        
        assert ticket is None

    async def test_save_ticket(self, manager):
        """Should save ticket changes."""
        await manager.initialize()
        ticket = await manager.create_ticket(
            id="TEST-001",
            title="Test",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        ticket.status = TicketStatus.IN_PROGRESS
        await manager.save_ticket(ticket)
        
        # Reload and verify
        reloaded = manager.get_ticket("TEST-001")
        assert reloaded.status == TicketStatus.IN_PROGRESS

    async def test_get_all_tickets(self, manager):
        """Should return all tickets."""
        await manager.initialize()
        await manager.create_ticket(
            id="TEST-001",
            title="First",
            description="First ticket",
            type="feature",
            priority="medium",
        )
        await manager.create_ticket(
            id="TEST-002",
            title="Second",
            description="Second ticket",
            type="bug",
            priority="high",
        )
        
        tickets = manager.get_all_tickets()
        
        assert len(tickets) == 2

    async def test_get_tickets_by_status(self, manager):
        """Should filter tickets by status."""
        await manager.initialize()
        await manager.create_ticket(
            id="TEST-001",
            title="Test",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        backlog_tickets = manager.get_tickets_by_status(TicketStatus.BACKLOG)
        progress_tickets = manager.get_tickets_by_status(TicketStatus.IN_PROGRESS)
        
        assert len(backlog_tickets) == 1
        assert len(progress_tickets) == 0

    async def test_get_next_ticket_for_refinement(self, manager):
        """Should return highest priority ticket for refinement."""
        await manager.initialize()
        
        # Create tickets with different priorities
        await manager.create_ticket(
            id="LOW-001",
            title="Low Priority",
            description="Low",
            type="feature",
            priority="low",
        )
        await manager.create_ticket(
            id="HIGH-001",
            title="High Priority",
            description="High",
            type="feature",
            priority="high",
        )
        
        next_ticket = manager.get_next_ticket_for_refinement()
        
        assert next_ticket is not None
        assert next_ticket.priority == Priority.HIGH

    async def test_ticket_file_created(self, manager, backlog_dir):
        """Should create ticket YAML file."""
        await manager.initialize()
        await manager.create_ticket(
            id="TEST-001",
            title="Test",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        ticket_file = backlog_dir / "tickets" / "TEST-001.yaml"
        assert ticket_file.exists()

    async def test_add_comment(self, manager):
        """Should add comment to ticket."""
        await manager.initialize()
        ticket = await manager.create_ticket(
            id="TEST-001",
            title="Test",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        ticket.add_comment("test_agent", "This is a comment")
        await manager.save_ticket(ticket)
        
        reloaded = manager.get_ticket("TEST-001")
        assert len(reloaded.comments) == 1
        assert reloaded.comments[0].message == "This is a comment"

    async def test_get_sprint_summary(self, manager):
        """Should return sprint summary."""
        await manager.initialize()
        await manager.create_ticket(
            id="TEST-001",
            title="Test",
            description="Test",
            type="feature",
            priority="medium",
        )
        
        summary = manager.get_sprint_summary()
        
        assert "total_tickets" in summary
        assert "status_breakdown" in summary
