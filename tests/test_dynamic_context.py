
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.base_agent import BaseAgent
from core.models import AgentMessage

class TestAgent(BaseAgent):
    """Concrete agent for testing."""
    async def process_task(self, message):
        return None

def test_dynamic_context_update():
    """Test that system prompt updates when context changes."""
    
    # 1. Init Agent
    agent = TestAgent(
        name="test",
        client=AsyncMock(),
        backlog=MagicMock(),
        message_bus=MagicMock(),
        system_prompt="ROLE: You are a tester."
    )
    
    # Verify Initial State
    initial_prompt = agent.system_prompt
    assert "ROLE: You are a tester." in initial_prompt
    assert "Projektkontext" not in initial_prompt
    
    # 2. Update Context
    new_context = "PROJECT: The project is about testing."
    agent.update_context(new_context)
    
    # Verify Updated State
    updated_prompt = agent.system_prompt
    assert "ROLE: You are a tester." in updated_prompt
    assert "Projektkontext" in updated_prompt
    assert new_context in updated_prompt
    
    # 3. Update Again
    agent.update_context("PROJECT: Changed.")
    assert "PROJECT: Changed." in agent.system_prompt
