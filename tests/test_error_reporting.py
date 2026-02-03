
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from agents.base_agent import BaseAgent
from tools.base import Tool, ToolResult, ToolResultStatus, ToolRegistry

class FailingTool(Tool):
    name = "fail_tool"
    description = "Always fails"
    async def execute(self, **kwargs):
        raise ValueError("Simulated Failure")

class MockAgent(BaseAgent):
    async def process_task(self, message): pass

@pytest.fixture
def agent():
    client = AsyncMock()
    # Mock LLM response to call the tool 3 times? 
    # Actually _call_llm_with_tools handles the loop internally for *one* tool call if retries happen.
    # We just need to trigger one tool call that fails 3 times (initial + 2 retries).
    
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
    client.chat.completions.create.return_value = response
    
    registry = ToolRegistry()
    registry.register(FailingTool())
    
    return MockAgent(
        name="test_agent",
        client=client,
        backlog=MagicMock(),
        message_bus=MagicMock(),
        system_prompt="Test Prompt",
        tools=registry
    )

@pytest.mark.asyncio
async def test_critical_failure_message(agent):
    """Test that max retries result in a CRITICAL_FAILURE message."""
    
    # We need to mock the client to return NO tool calls on the SECOND call 
    # (after the tool results are fed back), so the loop terminates.
    # But wait, _call_llm_with_tools loops based on LLM response.
    # If we want to test the retry logic INSIDE the loop, we just need one LLM response.
    # The retry logic (for attempt in range(max_retries + 1)) is inside the loop over tool_calls.
    
    # So we act as if the LLM requested 'fail_tool'.
    # The code will try to execute it 3 times (0, 1, 2).
    # Then it appends the result to 'messages'.
    # We want to inspect the last message appended to 'messages' list inside the agent.
    # Since we can't easily inspect local vars, we can capture the return value of execute_tool 
    # OR simpler: check the log calls?
    
    # Let's check the result passed back to the LLM history.
    # We can mock the client.chat.completions.create to inspect the 'messages' arg passed in the NEXT call?
    # OR we can just rely on the return value if the loop finishes.
    
    # Let's mock the client to return a "final" response (no tool calls) on the second invocation.
    
    final_message = MagicMock()
    final_message.tool_calls = None
    final_message.content = "Final Answer"
    
    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message = final_message
    
    # Initial call returns tool call, Second call returns final answer
    agent.client.chat.completions.create.side_effect = [
        agent.client.chat.completions.create.return_value, # The tool call setup in fixture
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
