"""Tests for agents module."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from agents.base_agent import BaseAgent
from agents import (
    ScrumMasterAgent,
    ProductOwnerAgent,
    ArchitectAgent,
    FrontendDevAgent,
    BackendDevAgent,
)
from core.models import (
    Ticket,
    TicketType,
    TicketStatus,
    Priority,
    AgentMessage,
    AgentResponse,
    MessageType,
    TechnicalContext,
    UserStory,
    RelatedFile,
)
from core.backlog import BacklogManager
from core.message_bus import MessageBus
from tools.base import ToolRegistry, Tool, ToolResult, ToolResultStatus


# === Fixtures ===

@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    
    # Mock response
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Mocked LLM response"
    mock_message.tool_calls = None
    mock_response.choices = [MagicMock(message=mock_message)]
    
    # Make it async
    async_mock = AsyncMock(return_value=mock_response)
    client.chat.completions.create = async_mock
    
    return client


@pytest.fixture
def message_bus():
    """Create a message bus instance."""
    return MessageBus()


@pytest_asyncio.fixture
async def backlog_manager(temp_dir):
    """Create a backlog manager with temp directory."""
    manager = BacklogManager(backlog_path=temp_dir)
    await manager.initialize()
    return manager


@pytest.fixture
def sample_ticket():
    """Create a sample ticket for testing."""
    return Ticket(
        id="TEST-001",
        type=TicketType.FEATURE,
        title="Test Feature",
        description="Implement a test feature",
        priority=Priority.MEDIUM,
        status=TicketStatus.BACKLOG,
        acceptance_criteria=[
            "Feature works correctly",
            "Tests pass",
        ],
        technical_context=TechnicalContext(
            affected_areas=["backend", "api"],
            related_files=[
                RelatedFile(path="src/api.py", reason="Main API file")
            ],
            implementation_notes="Use async patterns",
        ),
        user_story=UserStory(
            as_a="Developer",
            i_want="a working feature",
            so_that="users can benefit",
        ),
    )


@pytest.fixture
def tool_registry():
    """Create a tool registry with mock tools."""
    registry = ToolRegistry()
    
    # Create a simple mock tool
    mock_tool = MagicMock(spec=Tool)
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.parameters = {"test_param": {"type": "string"}}
    mock_tool.validate_params = MagicMock(return_value=(True, None))
    mock_tool.execute = AsyncMock(return_value=ToolResult(
        status=ToolResultStatus.SUCCESS,
        output={"result": "success"},
        error=None,
    ))
    mock_tool.get_schema = MagicMock(return_value={
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {"test_param": {"type": "string"}},
            },
        },
    })
    
    registry.register(mock_tool)
    return registry


# === Concrete Test Agent ===

class ConcreteTestAgent(BaseAgent):
    """Concrete implementation for testing BaseAgent."""
    
    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Simple task processing for tests."""
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=message.ticket_id,
            action_taken="task_processed",
            message="Task processed successfully",
        )


@pytest.fixture
def test_agent(mock_openai_client, backlog_manager, message_bus):
    """Create a test agent instance."""
    return ConcreteTestAgent(
        name="test_agent",
        client=mock_openai_client,
        backlog=backlog_manager,
        message_bus=message_bus,
        system_prompt="You are a test agent.",
        model="gpt-4o",
        temperature=0.3,
    )


# === BaseAgent Tests ===

class TestBaseAgentInit:
    """Test BaseAgent initialization."""
    
    def test_agent_created_with_correct_attributes(self, test_agent):
        """Agent should be created with correct attributes."""
        assert test_agent.name == "test_agent"
        assert test_agent.model == "gpt-4o"
        assert test_agent.temperature == 0.3
        assert test_agent.system_prompt == "You are a test agent."
    
    def test_agent_registered_with_message_bus(self, test_agent, message_bus):
        """Agent should register with message bus on init."""
        assert "test_agent" in message_bus._subscriptions
    
    def test_agent_with_tools(self, mock_openai_client, backlog_manager, message_bus, tool_registry):
        """Agent should accept tool registry."""
        agent = ConcreteTestAgent(
            name="tool_agent",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent with tools",
            tools=tool_registry,
        )
        assert agent.tools is not None
        assert agent.tools.get("test_tool") is not None


class TestBaseAgentMessageHandling:
    """Test message handling functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_task_message(self, test_agent):
        """Agent should handle TASK messages."""
        message = AgentMessage(
            from_agent="other_agent",
            to_agent="test_agent",
            message_type=MessageType.TASK,
            content="Do something",
            ticket_id="TEST-001",
        )
        
        response = await test_agent.handle_message(message)
        
        assert response is not None
        assert response.success is True
        assert response.action_taken == "task_processed"
    
    @pytest.mark.asyncio
    async def test_handle_question_message(self, test_agent, mock_openai_client):
        """Agent should handle QUESTION messages."""
        message = AgentMessage(
            from_agent="other_agent",
            to_agent="test_agent",
            message_type=MessageType.QUESTION,
            content="What is the status?",
        )
        
        response = await test_agent.handle_message(message)
        
        assert response is not None
        assert response.success is True
        assert response.action_taken == "question_answered"
        mock_openai_client.chat.completions.create.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_update_message(self, test_agent):
        """Agent should handle UPDATE messages."""
        message = AgentMessage(
            from_agent="other_agent",
            to_agent="test_agent",
            message_type=MessageType.UPDATE,
            content="Status update",
        )
        
        response = await test_agent.handle_message(message)
        
        assert response is not None
        assert response.success is True
        assert response.action_taken == "update_acknowledged"
    
    @pytest.mark.asyncio
    async def test_handle_handoff_message(self, test_agent):
        """Agent should handle HANDOFF messages."""
        message = AgentMessage(
            from_agent="other_agent",
            to_agent="test_agent",
            message_type=MessageType.HANDOFF,
            content="Take over this task",
            ticket_id="TEST-001",
        )
        
        response = await test_agent.handle_message(message)
        
        assert response is not None
        assert response.success is True
        # Default handoff behavior delegates to process_task
        assert response.action_taken == "task_processed"


class TestBaseAgentLLMCalls:
    """Test LLM call functionality."""
    
    @pytest.mark.asyncio
    async def test_call_llm_basic(self, test_agent, mock_openai_client):
        """_call_llm should make proper LLM call."""
        response = await test_agent._call_llm("Test message")
        
        assert response == "Mocked LLM response"
        mock_openai_client.chat.completions.create.assert_called_once()
        
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o"
        assert call_args.kwargs["temperature"] == 0.3
    
    @pytest.mark.asyncio
    async def test_call_llm_with_ticket_context(self, test_agent, mock_openai_client, sample_ticket):
        """_call_llm should include ticket context."""
        response = await test_agent._call_llm(
            "Process this ticket",
            ticket=sample_ticket,
        )
        
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        
        # User message should contain ticket info
        user_message = messages[1]["content"]
        assert "TEST-001" in user_message
        assert "Test Feature" in user_message
    
    @pytest.mark.asyncio
    async def test_call_llm_with_additional_context(self, test_agent, mock_openai_client):
        """_call_llm should include additional context."""
        response = await test_agent._call_llm(
            "Process this",
            additional_context="Extra context here",
        )
        
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        
        user_message = messages[1]["content"]
        assert "Extra context here" in user_message
    
    @pytest.mark.asyncio
    async def test_call_llm_json(self, test_agent, mock_openai_client):
        """_call_llm_json should parse JSON response."""
        # Mock a JSON response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '{"key": "value", "number": 42}'
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = await test_agent._call_llm_json("Return JSON")
        
        assert result == {"key": "value", "number": 42}
    
    @pytest.mark.asyncio
    async def test_call_llm_json_with_code_blocks(self, test_agent, mock_openai_client):
        """_call_llm_json should handle JSON in code blocks."""
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '```json\n{"key": "value"}\n```'
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = await test_agent._call_llm_json("Return JSON")
        
        assert result == {"key": "value"}


class TestBaseAgentToolCalls:
    """Test tool calling functionality."""
    
    @pytest.mark.asyncio
    async def test_call_llm_with_tools_no_tools_available(self, test_agent):
        """Should fallback to regular LLM call when no tools."""
        response, tool_results = await test_agent._call_llm_with_tools("Do something")
        
        assert response == "Mocked LLM response"
        assert tool_results == []
    
    @pytest.mark.asyncio
    async def test_call_llm_with_tools_executes_tool(
        self, mock_openai_client, backlog_manager, message_bus, tool_registry
    ):
        """Should execute tools when LLM requests them."""
        agent = ConcreteTestAgent(
            name="tool_agent",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent with tools",
            tools=tool_registry,
        )
        
        # First call: LLM returns tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"test_param": "value"}'
        
        first_response = MagicMock()
        first_message = MagicMock()
        first_message.content = None
        first_message.tool_calls = [mock_tool_call]
        first_response.choices = [MagicMock(message=first_message)]
        
        # Second call: LLM returns final response
        second_response = MagicMock()
        second_message = MagicMock()
        second_message.content = "Tool executed successfully"
        second_message.tool_calls = None
        second_response.choices = [MagicMock(message=second_message)]
        
        mock_openai_client.chat.completions.create.side_effect = [
            first_response, second_response
        ]
        
        response, tool_results = await agent._call_llm_with_tools("Use the tool")
        
        assert response == "Tool executed successfully"
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "test_tool"
        assert tool_results[0]["success"] is True
    
    @pytest.mark.asyncio
    async def test_execute_tool_directly(
        self, mock_openai_client, backlog_manager, message_bus, tool_registry
    ):
        """Should execute tool directly via execute_tool method."""
        agent = ConcreteTestAgent(
            name="tool_agent",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent with tools",
            tools=tool_registry,
        )
        
        result = await agent.execute_tool("test_tool", test_param="value")
        
        assert result.success is True
        assert result.output == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(
        self, mock_openai_client, backlog_manager, message_bus, tool_registry
    ):
        """Should return error for non-existent tool."""
        agent = ConcreteTestAgent(
            name="tool_agent",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent with tools",
            tools=tool_registry,
        )
        
        result = await agent.execute_tool("nonexistent_tool")
        
        assert result.success is False
        assert "nicht gefunden" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_tool_no_registry(self, test_agent):
        """Should return error when no tool registry."""
        result = await test_agent.execute_tool("any_tool")
        
        assert result.success is False
        assert "Keine Tools verfügbar" in result.error


class TestBaseAgentCommunication:
    """Test inter-agent communication."""
    
    @pytest.mark.asyncio
    async def test_ask_agent(self, mock_openai_client, backlog_manager, message_bus):
        """Should ask another agent and get response."""
        # Create two agents
        agent1 = ConcreteTestAgent(
            name="agent1",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 1",
        )
        agent2 = ConcreteTestAgent(
            name="agent2",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 2",
        )
        
        response = await agent1.ask_agent("agent2", "What is your status?")
        
        assert response == "Mocked LLM response"
    
    @pytest.mark.asyncio
    async def test_handoff_to(self, mock_openai_client, backlog_manager, message_bus):
        """Should hand off task to another agent."""
        agent1 = ConcreteTestAgent(
            name="agent1",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 1",
        )
        agent2 = ConcreteTestAgent(
            name="agent2",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 2",
        )
        
        response = await agent1.handoff_to(
            "agent2",
            "Take over this task",
            ticket_id="TEST-001",
        )
        
        assert response is not None
        assert response.success is True
        assert response.agent == "agent2"
    
    @pytest.mark.asyncio
    async def test_broadcast_update(self, mock_openai_client, backlog_manager, message_bus):
        """Should broadcast update to all agents."""
        agent1 = ConcreteTestAgent(
            name="agent1",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 1",
        )
        # Create a second agent so broadcast has someone to send to
        agent2 = ConcreteTestAgent(
            name="agent2",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Agent 2",
        )
        
        # This should not raise
        await agent1.broadcast_update("Status update")
        
        # Broadcast queues messages, so we verify at least subscriptions exist
        assert "agent1" in message_bus._subscriptions
        assert "agent2" in message_bus._subscriptions


class TestBaseAgentTicketFormatting:
    """Test ticket context formatting."""
    
    def test_format_ticket_context_basic(self, test_agent, sample_ticket):
        """Should format basic ticket info."""
        context = test_agent._format_ticket_context(sample_ticket)
        
        assert "TEST-001" in context
        assert "Test Feature" in context
        assert "feature" in context.lower()
        assert "medium" in context.lower()
    
    def test_format_ticket_context_with_acceptance_criteria(self, test_agent, sample_ticket):
        """Should include acceptance criteria."""
        context = test_agent._format_ticket_context(sample_ticket)
        
        assert "Acceptance Criteria" in context
        assert "Feature works correctly" in context
        assert "Tests pass" in context
    
    def test_format_ticket_context_with_user_story(self, test_agent, sample_ticket):
        """Should include user story."""
        context = test_agent._format_ticket_context(sample_ticket)
        
        assert "User Story" in context
        assert "Developer" in context
        assert "working feature" in context
    
    def test_format_ticket_context_with_technical_context(self, test_agent, sample_ticket):
        """Should include technical context."""
        context = test_agent._format_ticket_context(sample_ticket)
        
        assert "Technischer Kontext" in context
        assert "backend" in context
        assert "src/api.py" in context


class TestBaseAgentGitOperations:
    """Test git-related safety operations."""
    
    @pytest.mark.asyncio
    async def test_check_git_status_no_tools(self, test_agent):
        """Should return error when no tools available."""
        result = await test_agent._check_git_status()
        
        assert result["has_changes"] is False
        assert result["error"] == "Keine Tools verfügbar"
    
    @pytest.mark.asyncio
    async def test_rollback_changes_no_tools(self, test_agent):
        """Should return error when no tools available."""
        result = await test_agent._rollback_changes()
        
        assert result["success"] is False
        assert "verfügbar" in result["message"].lower() or "tool" in result["message"].lower()


# === Specialized Agent Tests ===

class TestScrumMasterAgent:
    """Test ScrumMasterAgent specific functionality."""
    
    @pytest.fixture
    def scrum_master(self, mock_openai_client, backlog_manager, message_bus, tool_registry):
        """Create ScrumMasterAgent instance."""
        return ScrumMasterAgent(
            name="scrum_master",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Scrum Master.",
            tools=tool_registry,
        )
    
    def test_scrum_master_has_correct_name(self, scrum_master):
        """ScrumMaster should have correct name."""
        assert scrum_master.name == "scrum_master"
    
    @pytest.mark.asyncio
    async def test_scrum_master_process_task(self, scrum_master, mock_openai_client):
        """ScrumMaster should process tasks."""
        message = AgentMessage(
            from_agent="product_owner",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Prioritize the backlog",
            ticket_id="TEST-001",
        )
        
        response = await scrum_master.process_task(message)
        
        assert response is not None
        assert response.agent == "scrum_master"
    
    @pytest.mark.asyncio
    async def test_select_next_ticket_no_tickets(self, scrum_master):
        """Should return no_tickets_available when backlog is empty."""
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Select next ticket",
            context={"task_type": "select_next_ticket"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "no_tickets_available"
        assert "Keine Tickets" in response.message
    
    @pytest.mark.asyncio
    async def test_select_next_ticket_with_planned_ticket(self, scrum_master, sample_ticket):
        """Should select planned ticket for work."""
        # Add planned ticket to backlog
        sample_ticket.status = TicketStatus.PLANNED
        sample_ticket.acceptance_criteria = ["AC1", "AC2"]
        sample_ticket.technical_context.affected_areas = ["backend"]
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Select next ticket",
            context={"task_type": "select_next_ticket"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "ticket_selected_for_work"
        assert response.ticket_id == "TEST-001"
        assert response.next_agent == "architect"
    
    @pytest.mark.asyncio
    async def test_select_next_ticket_needs_refinement(self, scrum_master, sample_ticket):
        """Should select backlog ticket for refinement."""
        # Add backlog ticket (not refined)
        sample_ticket.status = TicketStatus.BACKLOG
        sample_ticket.acceptance_criteria = []  # Not refined
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Select next ticket",
            context={"task_type": "select_next_ticket"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "ticket_selected_for_refinement"
        assert response.next_agent == "product_owner"
    
    @pytest.mark.asyncio
    async def test_start_refinement_no_ticket_id(self, scrum_master):
        """Should fail when no ticket_id provided."""
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Start refinement",
            context={"task_type": "start_refinement"},
            ticket_id=None,
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "refinement_failed"
        assert "Keine Ticket-ID" in response.message
    
    @pytest.mark.asyncio
    async def test_start_refinement_ticket_not_found(self, scrum_master):
        """Should fail when ticket doesn't exist."""
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Start refinement",
            context={"task_type": "start_refinement"},
            ticket_id="NONEXISTENT-999",
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "refinement_failed"
        assert "nicht gefunden" in response.message
    
    @pytest.mark.asyncio
    async def test_check_blockers_none(self, scrum_master):
        """Should report no blockers when none exist."""
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Check blockers",
            context={"task_type": "check_blockers"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "blocker_check"
        assert response.result["blocked_count"] == 0
    
    @pytest.mark.asyncio
    async def test_check_blockers_with_blocked_tickets(self, scrum_master, sample_ticket):
        """Should analyze blocked tickets."""
        # Add blocked ticket
        sample_ticket.status = TicketStatus.BLOCKED
        sample_ticket.dependencies.blocked_by = ["OTHER-001"]
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Check blockers",
            context={"task_type": "check_blockers"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "blocker_analysis"
        assert response.result["blocked_count"] == 1
    
    @pytest.mark.asyncio
    async def test_sprint_planning_no_tickets(self, scrum_master):
        """Should fail when no refined tickets available."""
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Sprint planning",
            context={"task_type": "sprint_planning"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "sprint_planning_failed"
    
    @pytest.mark.asyncio
    async def test_orchestrate_delegates_in_progress_to_assigned_dev(self, scrum_master, sample_ticket):
        """Should delegate in_progress ticket to assigned developer."""
        sample_ticket.status = TicketStatus.IN_PROGRESS
        sample_ticket.implementation.assigned_to = "backend_dev"
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Orchestrate",
            context={"task_type": "orchestrate"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "delegating_to_developer"
        assert response.next_agent == "backend_dev"
    
    @pytest.mark.asyncio
    async def test_orchestrate_delegates_review_to_architect(self, scrum_master, sample_ticket):
        """Should delegate REVIEW ticket to architect for code review."""
        sample_ticket.status = TicketStatus.REVIEW
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Orchestrate",
            context={"task_type": "orchestrate"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "delegating_to_review"
        assert response.next_agent == "architect"
    
    @pytest.mark.asyncio
    async def test_assign_developer_backend(self, scrum_master, sample_ticket):
        """Should assign backend_dev for backend tasks."""
        sample_ticket.status = TicketStatus.IN_PROGRESS
        sample_ticket.implementation.assigned_to = None  # Not assigned
        sample_ticket.technical_context.affected_areas = ["api", "database"]
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="system",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Orchestrate",
            context={"task_type": "orchestrate"},
        )
        
        response = await scrum_master.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "developer_assigned"
        assert response.next_agent == "backend_dev"
    
    @pytest.mark.asyncio
    async def test_loop_detection_blocks_ticket_after_max_cycles(self, scrum_master, sample_ticket):
        """Should block ticket after MAX_CYCLES_PER_TICKET cycles."""
        sample_ticket.status = TicketStatus.REVIEW
        await scrum_master.backlog.save_ticket(sample_ticket)
        
        # Reset counter from previous tests (class variable persists)
        scrum_master._ticket_cycle_counts.clear()
        
        # Simulate multiple cycles
        for i in range(scrum_master.MAX_CYCLES_PER_TICKET + 1):
            result = await scrum_master._check_and_handle_loop(sample_ticket)
            if i < scrum_master.MAX_CYCLES_PER_TICKET:
                assert result is False, f"Should not block at cycle {i+1}"
            else:
                assert result is True, f"Should block at cycle {i+1}"
        
        # Ticket should now be blocked
        updated_ticket = scrum_master.backlog.get_ticket(sample_ticket.id)
        assert updated_ticket.status == TicketStatus.BLOCKED
    
    def test_reset_cycle_counter(self, scrum_master, sample_ticket):
        """Should reset cycle counter for ticket."""
        scrum_master._ticket_cycle_counts[sample_ticket.id] = 3
        
        scrum_master.reset_cycle_counter(sample_ticket.id)
        
        assert sample_ticket.id not in scrum_master._ticket_cycle_counts


class TestProductOwnerAgent:
    """Test ProductOwnerAgent specific functionality."""
    
    @pytest.fixture
    def product_owner(self, mock_openai_client, backlog_manager, message_bus, tool_registry):
        """Create ProductOwnerAgent instance."""
        return ProductOwnerAgent(
            name="product_owner",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Product Owner.",
            tools=tool_registry,
        )
    
    def test_product_owner_has_correct_name(self, product_owner):
        """ProductOwner should have correct name."""
        assert product_owner.name == "product_owner"
    
    @pytest.mark.asyncio
    async def test_refine_ticket_no_ticket_id(self, product_owner):
        """Should fail when no ticket_id provided."""
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="product_owner",
            message_type=MessageType.TASK,
            content="Refine ticket",
            ticket_id=None,
        )
        
        response = await product_owner.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "refinement_failed"
        assert "Keine Ticket-ID" in response.message
    
    @pytest.mark.asyncio
    async def test_refine_ticket_not_found(self, product_owner):
        """Should fail when ticket doesn't exist."""
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="product_owner",
            message_type=MessageType.TASK,
            content="Refine ticket",
            ticket_id="NONEXISTENT-999",
        )
        
        response = await product_owner.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "refinement_failed"
        assert "nicht gefunden" in response.message
    
    @pytest.mark.asyncio
    async def test_refine_ticket_success(self, product_owner, sample_ticket, mock_openai_client):
        """Should successfully refine ticket."""
        # Setup mock response for refinement
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "acceptance_criteria": ["AC1", "AC2", "AC3"],
            "user_story": {
                "as_a": "User",
                "i_want": "feature",
                "so_that": "benefit",
            },
            "refinement_notes": "Ready for dev",
        })
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Save ticket first
        await product_owner.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="product_owner",
            message_type=MessageType.TASK,
            content="Refine ticket",
            ticket_id="TEST-001",
        )
        
        response = await product_owner.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "ticket_refined"
        assert response.next_agent == "architect"
        assert len(response.result["acceptance_criteria"]) == 3
    
    @pytest.mark.asyncio
    async def test_validate_no_ticket_id(self, product_owner):
        """Should fail validation when no ticket_id."""
        message = AgentMessage(
            from_agent="backend_dev",
            to_agent="product_owner",
            message_type=MessageType.TASK,
            content="Validate implementation",
            context={"task_type": "validate"},
            ticket_id=None,
        )
        
        response = await product_owner.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "validation_failed"
    
    @pytest.mark.asyncio
    async def test_validate_wrong_status(self, product_owner, sample_ticket):
        """Should fail validation when ticket not in REVIEW status."""
        sample_ticket.status = TicketStatus.IN_PROGRESS
        await product_owner.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="backend_dev",
            to_agent="product_owner",
            message_type=MessageType.TASK,
            content="Validate implementation",
            context={"task_type": "validate"},
            ticket_id="TEST-001",
        )
        
        response = await product_owner.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "validation_failed"
        assert "nicht im Review-Status" in response.message
    
    @pytest.mark.asyncio
    async def test_handle_handoff_refine(self, product_owner, sample_ticket, mock_openai_client):
        """Should handle handoff for refinement."""
        # Setup mock
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "acceptance_criteria": ["AC1"],
            "user_story": {"as_a": "U", "i_want": "F", "so_that": "B"},
        })
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        await product_owner.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="product_owner",
            message_type=MessageType.HANDOFF,
            content="Bitte verfeinere dieses Ticket",
            ticket_id="TEST-001",
        )
        
        response = await product_owner.handle_handoff(message)
        
        assert response.success is True
        assert response.action_taken == "ticket_refined"
    
    @pytest.mark.asyncio
    async def test_handle_handoff_validates_review_status(self, product_owner, sample_ticket, mock_openai_client):
        """Should automatically validate when ticket is in REVIEW status."""
        # Setup mock for validation
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "validation_results": [{"criterion": "AC1", "passed": True, "evidence": "Works"}],
            "overall_passed": True,
            "feedback": "All good",
        })
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        sample_ticket.status = TicketStatus.REVIEW
        sample_ticket.acceptance_criteria = ["AC1"]
        await product_owner.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="architect",
            to_agent="product_owner",
            message_type=MessageType.HANDOFF,
            content="Code-Review bestanden",
            ticket_id="TEST-001",
        )
        
        response = await product_owner.handle_handoff(message)
        
        assert response.action_taken == "validation_complete"
    
    @pytest.mark.asyncio
    async def test_read_implementation_files_with_tools(self, product_owner, sample_ticket):
        """Should read implementation files using tools."""
        # Mock read_file tool is already in tool_registry
        result = await product_owner._read_implementation_files(sample_ticket)
        
        # Should return some content (even if files not found)
        assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_read_implementation_files_without_tools(self, mock_openai_client, backlog_manager, message_bus):
        """Should handle case when no tools available."""
        product_owner = ProductOwnerAgent(
            name="product_owner",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Product Owner.",
            tools=None,  # No tools
        )
        
        from core.models import Ticket, TicketType
        ticket = Ticket(
            id="TEST-001",
            title="Test",
            description="Test ticket",
            type=TicketType.FEATURE,
        )
        
        result = await product_owner._read_implementation_files(ticket)
        
        assert "Keine Tools" in result
    
    @pytest.mark.asyncio
    async def test_run_tests_without_tools(self, mock_openai_client, backlog_manager, message_bus):
        """Should handle case when no tools available."""
        product_owner = ProductOwnerAgent(
            name="product_owner",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Product Owner.",
            tools=None,
        )
        
        result = await product_owner._run_tests_for_validation()
        
        assert "Keine Tools" in result


class TestArchitectAgent:
    """Test ArchitectAgent specific functionality."""
    
    @pytest.fixture
    def architect(self, mock_openai_client, backlog_manager, message_bus, tool_registry, temp_dir):
        """Create ArchitectAgent instance."""
        return ArchitectAgent(
            name="architect",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Software-Architekt.",
            tools=tool_registry,
            codebase_path=str(temp_dir),
        )
    
    def test_architect_has_correct_name(self, architect):
        """Architect should have correct name."""
        assert architect.name == "architect"
    
    def test_architect_has_codebase_path(self, architect, temp_dir):
        """Architect should have codebase_path set."""
        assert architect.codebase_path == temp_dir
    
    @pytest.mark.asyncio
    async def test_analyze_no_ticket_id(self, architect):
        """Should fail analysis when no ticket_id."""
        message = AgentMessage(
            from_agent="product_owner",
            to_agent="architect",
            message_type=MessageType.TASK,
            content="Analyze",
            ticket_id=None,
        )
        
        response = await architect.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "analysis_failed"
    
    @pytest.mark.asyncio
    async def test_analyze_ticket_not_found(self, architect):
        """Should fail when ticket doesn't exist."""
        message = AgentMessage(
            from_agent="product_owner",
            to_agent="architect",
            message_type=MessageType.TASK,
            content="Analyze",
            ticket_id="NONEXISTENT-999",
        )
        
        response = await architect.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "analysis_failed"
    
    @pytest.mark.asyncio
    async def test_analyze_and_plan_success(self, architect, sample_ticket, mock_openai_client):
        """Should successfully analyze and create plan."""
        # Setup mock response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "affected_areas": ["backend", "api"],
            "dependencies": ["pydantic"],
            "related_files": [{"path": "src/api.py", "reason": "Main API"}],
            "implementation_notes": "Use async",
            "subtasks": [{"id": "001-1", "description": "Create endpoint"}],
            "complexity": "medium",
            "story_points": 5,
            "risks": ["API breaking change"],
            "architectural_notes": "Consider versioning",
        })
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        await architect.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="product_owner",
            to_agent="architect",
            message_type=MessageType.TASK,
            content="Analyze and plan",
            ticket_id="TEST-001",
        )
        
        response = await architect.process_task(message)
        
        assert response.success is True
        assert response.action_taken == "technical_analysis_complete"
        assert "backend" in response.result.get("affected_areas", [])
    
    @pytest.mark.asyncio
    async def test_review_no_ticket_id(self, architect):
        """Should fail review when no ticket_id."""
        message = AgentMessage(
            from_agent="backend_dev",
            to_agent="architect",
            message_type=MessageType.TASK,
            content="Review code",
            context={"task_type": "review"},
            ticket_id=None,
        )
        
        response = await architect.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "review_failed"
    
    @pytest.mark.asyncio
    async def test_estimate_no_ticket_id(self, architect):
        """Should fail estimation when no ticket_id."""
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="architect",
            message_type=MessageType.TASK,
            content="Estimate",
            context={"task_type": "estimate"},
            ticket_id=None,
        )
        
        response = await architect.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "estimation_failed"
    
    @pytest.mark.asyncio
    async def test_handle_handoff_reviews_review_status(
        self, mock_openai_client, backlog_manager, message_bus, sample_ticket
    ):
        """Should automatically do code review when ticket is in REVIEW status."""
        # Create architect WITHOUT tools for simpler test
        architect = ArchitectAgent(
            name="architect",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Architekt.",
            tools=None,  # No tools = simpler code path
        )
        
        # Setup mock for review (without tools, only one LLM call)
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "approved": True,
            "quality_score": 8,
            "findings": [],
            "suggestions": [],
            "summary": "Good code",
        })
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        sample_ticket.status = TicketStatus.REVIEW
        await architect.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="scrum_master",
            to_agent="architect",
            message_type=MessageType.HANDOFF,
            content="Ticket wartet auf Review",
            ticket_id="TEST-001",
        )
        
        response = await architect.handle_handoff(message)
        
        assert response.action_taken == "code_review_complete"
        assert response.next_agent == "product_owner"


class TestFrontendDevAgent:
    """Test FrontendDevAgent specific functionality."""
    
    @pytest.fixture
    def frontend_dev(self, mock_openai_client, backlog_manager, message_bus, tool_registry):
        """Create FrontendDevAgent instance."""
        return FrontendDevAgent(
            name="frontend_dev",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Frontend-Entwickler.",
            tools=tool_registry,
        )
    
    def test_frontend_dev_has_correct_name(self, frontend_dev):
        """FrontendDev should have correct name."""
        assert frontend_dev.name == "frontend_dev"
    
    @pytest.mark.asyncio
    async def test_implement_no_ticket_id(self, frontend_dev):
        """Should fail implementation when no ticket_id."""
        message = AgentMessage(
            from_agent="architect",
            to_agent="frontend_dev",
            message_type=MessageType.TASK,
            content="Implement UI",
            ticket_id=None,
        )
        
        response = await frontend_dev.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "implementation_failed"
    
    @pytest.mark.asyncio
    async def test_implement_ticket_not_found(self, frontend_dev):
        """Should fail when ticket doesn't exist."""
        message = AgentMessage(
            from_agent="architect",
            to_agent="frontend_dev",
            message_type=MessageType.TASK,
            content="Implement UI",
            ticket_id="NONEXISTENT-999",
        )
        
        response = await frontend_dev.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "implementation_failed"
    
    @pytest.mark.asyncio
    async def test_implement_updates_ticket_status(self, frontend_dev, sample_ticket, mock_openai_client):
        """Should update ticket status to IN_PROGRESS."""
        # Mock tool calls response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Implementation complete"
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        sample_ticket.status = TicketStatus.PLANNED
        await frontend_dev.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="architect",
            to_agent="frontend_dev",
            message_type=MessageType.TASK,
            content="Implement UI",
            ticket_id="TEST-001",
        )
        
        await frontend_dev.process_task(message)
        
        # Verify ticket was assigned (status may be REVIEW after implementation)
        ticket = frontend_dev.backlog.get_ticket("TEST-001")
        assert ticket.status in [TicketStatus.IN_PROGRESS, TicketStatus.REVIEW]
        assert ticket.implementation.assigned_to == "frontend_dev"


class TestBackendDevAgent:
    """Test BackendDevAgent specific functionality."""
    
    @pytest.fixture
    def backend_dev(self, mock_openai_client, backlog_manager, message_bus, tool_registry):
        """Create BackendDevAgent instance."""
        return BackendDevAgent(
            name="backend_dev",
            client=mock_openai_client,
            backlog=backlog_manager,
            message_bus=message_bus,
            system_prompt="Du bist ein Backend-Entwickler.",
            tools=tool_registry,
        )
    
    def test_backend_dev_has_correct_name(self, backend_dev):
        """BackendDev should have correct name."""
        assert backend_dev.name == "backend_dev"
    
    @pytest.mark.asyncio
    async def test_implement_no_ticket_id(self, backend_dev):
        """Should fail implementation when no ticket_id."""
        message = AgentMessage(
            from_agent="architect",
            to_agent="backend_dev",
            message_type=MessageType.TASK,
            content="Implement API",
            ticket_id=None,
        )
        
        response = await backend_dev.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "implementation_failed"
    
    @pytest.mark.asyncio
    async def test_implement_ticket_not_found(self, backend_dev):
        """Should fail when ticket doesn't exist."""
        message = AgentMessage(
            from_agent="architect",
            to_agent="backend_dev",
            message_type=MessageType.TASK,
            content="Implement API",
            ticket_id="NONEXISTENT-999",
        )
        
        response = await backend_dev.process_task(message)
        
        assert response.success is False
        assert response.action_taken == "implementation_failed"
    
    @pytest.mark.asyncio
    async def test_implement_updates_ticket_status(self, backend_dev, sample_ticket, mock_openai_client):
        """Should update ticket status to IN_PROGRESS."""
        # Mock tool calls response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Implementation complete"
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        sample_ticket.status = TicketStatus.PLANNED
        await backend_dev.backlog.save_ticket(sample_ticket)
        
        message = AgentMessage(
            from_agent="architect",
            to_agent="backend_dev",
            message_type=MessageType.TASK,
            content="Implement API",
            ticket_id="TEST-001",
        )
        
        await backend_dev.process_task(message)
        
        # Verify ticket was assigned (status may be REVIEW after implementation)
        ticket = backend_dev.backlog.get_ticket("TEST-001")
        assert ticket.status in [TicketStatus.IN_PROGRESS, TicketStatus.REVIEW]
        assert ticket.implementation.assigned_to == "backend_dev"
