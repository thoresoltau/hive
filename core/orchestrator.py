"""Orchestrator - coordinates all agents and manages workflow."""

import asyncio
from pathlib import Path
from typing import Optional
import os

import yaml
from openai import AsyncOpenAI
from dotenv import load_dotenv

from .backlog import BacklogManager
from .message_bus import MessageBus
from .models import AgentMessage, AgentResponse, MessageType, TicketStatus
from .context import ContextManager
from .mcp import MCPClientManager
from .logging import get_logger
from tools.base import ToolRegistry


class Orchestrator:
    """
    Main orchestrator for the Hive Agent Swarm.
    
    Responsibilities:
    - Initialize all agents
    - Coordinate workflow between agents
    - Manage the main processing loop
    - Handle errors and recovery
    """

    def __init__(
        self,
        backlog_path: str | Path,
        config_path: str | Path,
        codebase_path: Optional[str | Path] = None,
    ):
        load_dotenv()
        
        self.backlog_path = Path(backlog_path)
        self.config_path = Path(config_path)
        self.codebase_path = Path(codebase_path) if codebase_path else None
        
        # Initialize core components
        from .global_config import GlobalConfigManager
        self.global_config = GlobalConfigManager()
        api_key = self.global_config.get_api_key("openai")
        
        if not api_key:
            self.log.warning("Kein OpenAI API Key gefunden. Bitte in ~/.hive/config.yaml oder als Environment Variable setzen.")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.backlog = BacklogManager(self.backlog_path)
        self.message_bus = MessageBus()
        self.context_manager = ContextManager(self.codebase_path) if self.codebase_path else None
        
        # Agents will be initialized later
        self.agents: dict = {}
        self._running = False
        
        # MCP Manager for external integrations (Context7, etc.)
        self.mcp_manager: Optional[MCPClientManager] = None
        self._config: dict = {}
        self._project_context: str = ""
        
        # Logger
        self.log = get_logger(verbose=True)

    async def initialize(self) -> None:
        """Initialize all components and agents."""
        # Load configuration
        with open(self.config_path) as f:
            self._config = yaml.safe_load(f)
        
        # Initialize backlog
        await self.backlog.initialize()
        
        # Load project context if available
        if self.context_manager and self.context_manager.is_initialized:
            self._project_context = await self.context_manager.get_full_context()
        
        # Initialize agents
        await self._initialize_agents()
        
        # Log initialization
        tools_count = len(self.tools.get_all()) if self.tools else 0
        self.log.workflow_start(
            project=str(self.codebase_path or self.backlog_path.parent),
            agents=list(self.agents.keys()),
            tools_count=tools_count,
        )

    async def _initialize_agents(self) -> None:
        """Initialize all agents from configuration."""
        from agents import (
            ScrumMasterAgent,
            ProductOwnerAgent,
            ArchitectAgent,
            FrontendDevAgent,
            BackendDevAgent,
        )
        
        agent_classes = {
            "scrum_master": ScrumMasterAgent,
            "product_owner": ProductOwnerAgent,
            "architect": ArchitectAgent,
            "frontend_dev": FrontendDevAgent,
            "backend_dev": BackendDevAgent,
        }
        
        agent_configs = self._config.get("agents", {})
        model_name = os.getenv("MODEL_NAME", "gpt-4o")
        
        # Create tool registry for all agents
        self.tools = None
        if self.codebase_path:
            self.tools = ToolRegistry()
            self.tools.register_defaults(workspace_path=str(self.codebase_path))
            
            # Initialize MCP and register MCP tools
            self.mcp_manager = MCPClientManager()
            mcp_count = self.mcp_manager.load_from_config()
            if mcp_count > 0:
                results = await self.mcp_manager.connect_all()
                connected = sum(1 for v in results.values() if v)
                if connected > 0:
                    mcp_tools = await self.tools.register_mcp_tools(self.mcp_manager)
                    self.log.debug(f"MCP: {connected} Server, {mcp_tools} Tools geladen")
        
        for agent_key, agent_class in agent_classes.items():
            config = agent_configs.get(agent_key, {})
            
            # Append project context to system prompt if available
            system_prompt = config.get("system_prompt", "")
            if self._project_context:
                system_prompt += f"\n\n## Projektkontext\n{self._project_context}"
            
            kwargs = {
                "name": agent_key,
                "client": self.client,
                "backlog": self.backlog,
                "message_bus": self.message_bus,
                "system_prompt": system_prompt,
                "model": config.get("model", model_name).replace("${MODEL_NAME}", model_name),
                "temperature": config.get("temperature", 0.3),
            }
            
            # All agents get file tools for documentation, tickets, etc.
            if self.tools:
                kwargs["tools"] = self.tools
            
            # Add codebase path for architect
            if agent_key == "architect" and self.codebase_path:
                kwargs["codebase_path"] = str(self.codebase_path)
            
            self.agents[agent_key] = agent_class(**kwargs)

    async def run_single_cycle(self) -> Optional[AgentResponse]:
        """Run a single workflow cycle."""
        # Start with Scrum Master selecting next action
        scrum_master = self.agents["scrum_master"]
        
        initial_message = AgentMessage(
            from_agent="orchestrator",
            to_agent="scrum_master",
            message_type=MessageType.TASK,
            content="Führe den nächsten Workflow-Schritt aus.",
            context={"task_type": "orchestrate"},
        )
        
        response = await scrum_master.handle_message(initial_message)
        
        if not response:
            return None
        
        # Follow the agent chain
        current_response = response
        max_hops = 10  # Prevent infinite loops
        hop_count = 0
        
        while current_response.next_agent and hop_count < max_hops:
            next_agent_name = current_response.next_agent
            next_agent = self.agents.get(next_agent_name)
            
            if not next_agent:
                self.log.warning(f"Agent '{next_agent_name}' nicht gefunden")
                break
            
            # Create handoff message
            handoff_message = AgentMessage(
                from_agent=current_response.agent,
                to_agent=next_agent_name,
                message_type=MessageType.HANDOFF,
                ticket_id=current_response.ticket_id,
                content=current_response.message or "",
                context=current_response.result,
            )
            
            self.log.agent_handoff(
                from_agent=current_response.agent,
                to_agent=next_agent_name,
                reason=current_response.message[:50] if current_response.message else "",
            )
            
            current_response = await next_agent.handle_message(handoff_message)
            
            if not current_response:
                break
            
            hop_count += 1
        
        return current_response

    async def run(self, max_cycles: int = 10) -> None:
        """Run the main orchestration loop."""
        self._running = True
        cycle = 0
        
        self.log.info("Starte Workflow...")
        
        while self._running and cycle < max_cycles:
            cycle += 1
            self.log.workflow_cycle_start(cycle, max_cycles)
            
            try:
                response = await self.run_single_cycle()
                
                if response:
                    self.log.workflow_cycle_end(
                        result=response.action_taken,
                        message=response.message,
                    )
                    
                    # Check if we're done (no more work)
                    if response.action_taken == "no_tickets_available":
                        self.log.info("Keine weiteren Tickets zu bearbeiten")
                        break
                else:
                    self.log.warning("Keine Antwort von Agents")
                    
            except Exception as e:
                self.log.error(f"Fehler in Zyklus {cycle}", exception=e)
                if self.log.verbose:
                    import traceback
                    traceback.print_exc()
            
            # Small delay between cycles
            await asyncio.sleep(1)
        
        # Print final summary
        summary = self.backlog.get_sprint_summary()
        self.log.workflow_finish(summary)

    async def stop(self) -> None:
        """Stop the orchestration loop."""
        self._running = False
        await self.message_bus.stop()
        
        # Disconnect MCP servers
        if self.mcp_manager:
            await self.mcp_manager.disconnect_all()

    async def process_ticket(self, ticket_id: str) -> AgentResponse:
        """Process a specific ticket through the workflow."""
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent="orchestrator",
                action_taken="ticket_not_found",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        # Determine starting point based on ticket status
        if ticket.status == TicketStatus.BACKLOG:
            start_agent = "product_owner"
            task = "Refinement"
        elif ticket.status == TicketStatus.REFINED:
            start_agent = "architect"
            task = "Technical Analysis"
        elif ticket.status == TicketStatus.PLANNED:
            start_agent = "backend_dev"
            task = "Implementation"
        elif ticket.status == TicketStatus.IN_PROGRESS:
            start_agent = ticket.implementation.assigned_to or "backend_dev"
            task = "Continue Implementation"
        elif ticket.status == TicketStatus.REVIEW:
            start_agent = "product_owner"
            task = "Validation"
        else:
            return AgentResponse(
                success=True,
                agent="orchestrator",
                ticket_id=ticket_id,
                action_taken="ticket_already_done",
                message=f"Ticket {ticket_id} ist bereits {ticket.status.value}.",
            )
        
        print(f"\n🎫 Processing {ticket_id}: {task}")
        print(f"   Starting with: {start_agent}")
        
        # Start processing
        agent = self.agents[start_agent]
        message = AgentMessage(
            from_agent="orchestrator",
            to_agent=start_agent,
            message_type=MessageType.TASK,
            ticket_id=ticket_id,
            content=f"Bearbeite Ticket {ticket_id}",
        )
        
        response = await agent.handle_message(message)
        
        # Follow chain
        current_response = response
        max_hops = 10
        hop_count = 0
        
        while current_response and current_response.next_agent and hop_count < max_hops:
            next_agent = self.agents.get(current_response.next_agent)
            if not next_agent:
                break
            
            handoff = AgentMessage(
                from_agent=current_response.agent,
                to_agent=current_response.next_agent,
                message_type=MessageType.HANDOFF,
                ticket_id=ticket_id,
                content=current_response.message or "",
                context=current_response.result,
            )
            
            print(f"   → {current_response.agent} → {current_response.next_agent}")
            current_response = await next_agent.handle_message(handoff)
            hop_count += 1
        
        return current_response
