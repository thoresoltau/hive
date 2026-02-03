
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from agents.observer import ObserverAgent
from core.models import AgentMessage, MessageType
from core.message_bus import MessageBus

@pytest.mark.asyncio
async def test_observer_monitoring():
    """Test that observer monitors messages and alerts on errors."""
    
    # 1. Setup
    bus = MessageBus()
    # Mock broadcast to capture alerts
    bus.broadcast = AsyncMock()
    
    observer = ObserverAgent(
        name="observer",
        client=AsyncMock(),
        backlog=MagicMock(),
        message_bus=bus,
        system_prompt="Observer Test"
    )
    
    # Initialize (subscribes to all)
    await observer.initialize()
    
    # 2. Simulate normal traffic
    msg_normal = AgentMessage(
        from_agent="A", to_agent="B", message_type=MessageType.TASK, content="Do work"
    )
    # Manually trigger callback (integration test would use bus.publish/send_direct)
    # But let's test the bus integration too by using bus public methods if possible?
    # bus.subscribe_to_all works?
    
    # Let's inject into bus monitors
    await bus._notify_monitors(msg_normal)
    import asyncio
    await asyncio.sleep(0.01) # Yield to event loop for create_task
    
    assert observer._message_count == 1
    
    # 3. Simulate Error Storm
    for i in range(5):
        msg_err = AgentMessage(
            from_agent="A", to_agent="B", 
            message_type=MessageType.RESPONSE, 
            content=f"CRITICAL_FAILURE: Failed {i}"
        )
        await bus._notify_monitors(msg_err)
        
    await asyncio.sleep(0.01) # Yield for error processing
        
    # 4. Verify Alert
    # Observer should have called broadcast with warning
    assert bus.broadcast.called
    call_args = bus.broadcast.call_args[1]
    assert "from_agent" in call_args and call_args["from_agent"] == "observer"
    assert "HIGH ERROR RATE" in call_args["content"]
