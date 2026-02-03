
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from core.orchestrator import Orchestrator
from core.models import AgentResponse, AgentMessage, MessageType

@pytest.fixture
def mock_orchestrator():
    """Create a mocked orchestrator."""
    with patch("core.orchestrator.BacklogManager"), \
         patch("core.orchestrator.AsyncOpenAI"), \
         patch("core.orchestrator.MessageBus"), \
         patch("core.orchestrator.ContextManager"), \
         patch("core.orchestrator.get_logger"):
        
        orch = Orchestrator(backlog_path=".", config_path="config.yaml")
        orch.agents = {}
        return orch

@pytest.mark.asyncio
async def test_loop_detection(mock_orchestrator):
    """Test that a ping-pong loop is detected and stopped."""
    
    # Mock Agents A and B
    agent_a = AsyncMock()
    agent_b = AsyncMock()
    
    mock_orchestrator.agents = {
        "scrum_master": agent_a, # Start here
        "agent_b": agent_b
    }
    
    # Setup Ping-Pong Loop
    # 1. Scrum Master (A) -> Agent B
    # 2. Agent B -> Scrum Master (A)
    # 3. ... repeat
    
    # Mock responses
    response_a_to_b = AgentResponse(
        success=True, agent="scrum_master", next_agent="agent_b",
        action_taken="pass", message="Go to B", ticket_id="T1"
    )
    
    response_b_to_a = AgentResponse(
        success=True, agent="agent_b", next_agent="scrum_master",
        action_taken="pass", message="Back to A", ticket_id="T1"
    )
    
    # Mock handle_message
    agent_a.handle_message.side_effect = [
        # Call 1 (Initial): Start -> B
        response_a_to_b,
        # Call 2 (Return from B): -> B again
        response_a_to_b,
        # Call 3: -> B again (Loop trigger?)
        response_a_to_b,
        # Call 4: -> B again
        response_a_to_b,
    ]
    
    agent_b.handle_message.return_value = response_b_to_a
    
    # Run single cycle
    result = await mock_orchestrator.run_single_cycle()
    
    # Assert loop was detected
    assert result is not None
    assert result.action_taken == "loop_detected"
    assert "Unendlicher Loop" in result.message
    
    # Debug info
    print(f"Result action: {result.action_taken}")
