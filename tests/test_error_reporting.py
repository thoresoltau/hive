
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def mock_openai_client():
    with patch("agents.base_agent.acompletion", new_callable=AsyncMock) as mock_acompletion:
        yield mock_acompletion

from agents.base_agent import BaseAgent
from tools.base import Tool, ToolRegistry

class FailingTool(Tool):
    name = "fail_tool"
    description = "Always fails"
    async def execute(self, **kwargs):
        raise ValueError("Simulated Failure")

class MockAgent(BaseAgent):
    async def process_task(self, message): pass

@pytest.fixture
def agent(mock_openai_client):

    # Setup tool call response
    message = MagicMock()
    message.tool_calls = [MagicMock()]
    message.tool_calls[0].function.name = "fail_tool"
    message.tool_calls[0].function.arguments = "{}"
    message.tool_calls[0].id = "call_123"
    message.content = None

    # Setup client response to return this message
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = message
    mock_openai_client.return_value = response

    registry = ToolRegistry()
    registry.register(FailingTool())

    return MockAgent(
        name="test_agent",
        backlog=MagicMock(),
        message_bus=MagicMock(),
        system_prompt="Test Prompt",
        tools=registry
    )

@pytest.mark.asyncio
async def test_critical_failure_message(agent, mock_openai_client):
    """Test that max retries result in a CRITICAL_FAILURE message."""

    final_message = MagicMock()
    final_message.tool_calls = None
    final_message.content = "Final Answer"

    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message = final_message

    # Initial call returns tool call, Second call returns final answer
    mock_openai_client.side_effect = [
        mock_openai_client.return_value, # The tool call setup in fixture
        final_response
    ]

    # Run
    response, tool_results = await agent._call_llm_with_tools("Do something")

    # Check tool results
    assert len(tool_results) == 1
    result = tool_results[0]

    print(f"Result: {result}")

    assert result["success"] is False
    assert "CRITICAL_FAILURE" in result["result"]
    assert "DO NOT RETRY" in result["result"]
    assert "Simulated Failure" in result["result"]
