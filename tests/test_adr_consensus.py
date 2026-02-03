
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from core.orchestrator import Orchestrator
from core.models import AgentResponse, AgentMessage, MessageType, TicketStatus

@pytest.fixture
def mock_orchestrator():
    """Create a mocked orchestrator."""
    with patch("core.orchestrator.BacklogManager"), \
         patch("core.orchestrator.AsyncOpenAI"), \
         patch("core.orchestrator.MessageBus"), \
         patch("core.orchestrator.ContextManager"), \
         patch("core.orchestrator.get_logger"), \
         patch("core.orchestrator.Orchestrator._initialize_agents"): # Prevent real agent init
        
        orch = Orchestrator(backlog_path=".", config_path="config.yaml")
        orch.agents = {}
        orch.tools = None # Explicitly set tools to None to avoid validation errors if accessed
        return orch

@pytest.mark.asyncio
async def test_adr_consensus_flow(mock_orchestrator):
    """Test that finding 'adr_proposed' triggers consensus."""
    
    # Mock Agents
    agent_scrum = AsyncMock()
    agent_architect = AsyncMock()
    agent_po = AsyncMock()
    agent_dev = AsyncMock()
    
    mock_orchestrator.agents = {
        "scrum_master": agent_scrum,
        "architect": agent_architect,
        "product_owner": agent_po,
        "backend_dev": agent_dev
    }
    
    # 1. Scrum Master -> Architect
    resp_scrum = AgentResponse(
        success=True, agent="scrum_master", next_agent="architect",
        action_taken="pass", message="Analyze ticket"
    )
    agent_scrum.handle_message.return_value = resp_scrum
    
    # 2. Architect -> Backend Dev (BUT with ADR proposed)
    resp_arch = AgentResponse(
        success=True, agent="architect", next_agent="backend_dev",
        action_taken="adr_proposed", # <--- TRIGGER
        message="ADR 001 Proposed",
        result={"architectural_notes": "Use Postgres"}
    )
    agent_architect.handle_message.return_value = resp_arch
    
    # 3. PO approves (mock response to consensus)
    resp_po = AgentResponse(
        success=True, agent="product_owner",
        action_taken="reply",
        message="I APPROVE this decision."
    )
    agent_po.handle_message.return_value = resp_po
    
    # 4. Backend Dev handles handoff
    resp_dev = AgentResponse(success=True, agent="backend_dev", action_taken="impl", message="Working")
    agent_dev.handle_message.return_value = resp_dev
    
    # Run Single Cycle
    # Since we mocked agents, we can run the real Orchestrator.run_single_cycle logic
    # We rely on the internal loop of run_single_cycle
    
    result = await mock_orchestrator.run_single_cycle()
    
    # Assertions
    # 1. Check if Architect was called
    assert agent_architect.handle_message.called
    
    # 2. Check if PO was called for Consensus (check arguments)
    assert agent_po.handle_message.called
    # Check the call args to verify it was a QUESTION about ADR
    call_args = agent_po.handle_message.call_args[0][0]
    assert call_args.message_type == MessageType.QUESTION
    assert "ADR PROPOSAL REVIEW REQUIRED" in call_args.content
    
    # 3. Check if loop continued to Backend Dev
    assert agent_dev.handle_message.called
