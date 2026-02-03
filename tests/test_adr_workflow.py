
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from agents.architect import ArchitectAgent
from core.models import AgentMessage, Ticket, TicketStatus, MessageType

@pytest.mark.asyncio
async def test_adr_generation_trigger():
    """Test that Architect generates ADR when architectural notes are significant."""
    
    # Mock Backlog
    mock_backlog = MagicMock()
    mock_ticket = MagicMock(spec=Ticket)
    mock_ticket.id = "T-100"
    mock_ticket.title = "Switch to Postgres"
    mock_ticket.description = "We need SQL."
    mock_ticket.status = TicketStatus.BACKLOG
    mock_ticket.technical_context = MagicMock()
    mock_ticket.implementation = MagicMock()
    
    mock_backlog.get_ticket.return_value = mock_ticket
    mock_backlog.save_ticket = AsyncMock()
    
    # Mock LLM Response for Analysis
    mock_analysis = {
        "complexity": "high",
        "story_points": 8,
        "affected_areas": ["database"],
        # Significant architectural note
        "architectural_notes": "We should use PostgreSQL instead of SQLite because of concurrent write requirements. This is a major change.",
        "risks": ["Migration"],
        "dependencies": [],
        "related_files": [],
        "subtasks": []
    }
    
    # Init Agent
    agent = ArchitectAgent(
        name="architect",
        client=AsyncMock(),
        backlog=mock_backlog,
        message_bus=MagicMock(),
        codebase_path="/tmp",
        system_prompt="Test Prompt"
    )
    
    # Mock LLM call to return our analysis
    agent._call_llm_json = AsyncMock(return_value=mock_analysis)
    
    # Mock _propose_adr to verify call flow
    with patch.object(agent, "_propose_adr", new_callable=AsyncMock) as mock_propose:
        mock_propose.return_value = "docs/adr/001-switch.md"
        
        # Action
        message = AgentMessage(
            from_agent="user",
            to_agent="architect",
            message_type=MessageType.TASK,
            ticket_id="T-100",
            content="Analyze this"
        )
        await agent._analyze_and_plan("T-100", "")
        
        # Assert
        mock_propose.assert_called_once()
        call_args = mock_propose.call_args[1]
        assert call_args["title"] == "Switch to Postgres"
        assert "PostgreSQL" in call_args["context"]
        
        # Check ticket comment
        assert mock_ticket.add_comment.called
        comment = mock_ticket.add_comment.call_args[0][1]
        assert "ADR Proposed" in comment
