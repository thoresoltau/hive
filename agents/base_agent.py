"""Base agent class for all specialized agents."""

from abc import ABC, abstractmethod
from typing import Optional, Any
import json

from openai import AsyncOpenAI

from core.models import (
    Ticket,
    AgentMessage,
    AgentResponse,
    MessageType,
)
from core.backlog import BacklogManager
from core.message_bus import MessageBus
from core.logging import get_logger
from tools.base import ToolRegistry, ToolResult


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the swarm.
    
    Each agent has:
    - A unique name/role
    - Access to the LLM client
    - Access to the backlog
    - Access to the message bus
    - A system prompt defining its role
    """

    def __init__(
        self,
        name: str,
        client: AsyncOpenAI,
        backlog: BacklogManager,
        message_bus: MessageBus,
        system_prompt: str,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        tools: Optional[ToolRegistry] = None,
    ):
        self.name = name
        self.client = client
        self.backlog = backlog
        self.message_bus = message_bus
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.tools = tools
        self.log = get_logger()
        
        # STABILITY PROTOCOL
        self.system_prompt += """

## STABILITY PROTOCOL
1. If a tool fails with "CRITICAL_FAILURE", DO NOT RETRY. Report the error immediately.
2. If you are stuck in a loop, STOP and ask for help.
3. Do not invent success. specific tools must return success=True.
"""
        
        # Register with message bus
        self.message_bus.subscribe(self.name, self.handle_message)

    async def handle_message(self, message: AgentMessage) -> Optional[AgentResponse]:
        """Handle incoming message from message bus."""
        # Log agent activity
        self.log.agent_start(self.name, message.ticket_id)
        
        if message.message_type == MessageType.TASK:
            response = await self.process_task(message)
        elif message.message_type == MessageType.QUESTION:
            response = await self.answer_question(message)
        elif message.message_type == MessageType.HANDOFF:
            response = await self.handle_handoff(message)
        else:
            response = await self.process_update(message)
        
        # Log completion
        if response:
            self.log.agent_complete(
                response.action_taken,
                response.success,
                response.message[:100] if response.message else "",
            )
        
        return response

    @abstractmethod
    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Process a task assignment. Must be implemented by subclasses."""
        pass

    async def answer_question(self, message: AgentMessage) -> AgentResponse:
        """Answer a question from another agent."""
        ticket = None
        if message.ticket_id:
            ticket = self.backlog.get_ticket(message.ticket_id)
        
        response = await self._call_llm(
            user_message=f"Frage von {message.from_agent}: {message.content}",
            ticket=ticket,
        )
        
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=message.ticket_id,
            action_taken="question_answered",
            result={"answer": response},
            message=response,
        )

    async def handle_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle a task handoff from another agent."""
        # Default: treat as new task
        return await self.process_task(message)

    async def process_update(self, message: AgentMessage) -> AgentResponse:
        """Process an update/notification."""
        # Default: acknowledge and log
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=message.ticket_id,
            action_taken="update_acknowledged",
            message=f"Update von {message.from_agent} erhalten.",
        )

    async def _call_llm(
        self,
        user_message: str,
        ticket: Optional[Ticket] = None,
        additional_context: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """Call the LLM with context."""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Build context
        context_parts = []
        
        if ticket:
            context_parts.append(self._format_ticket_context(ticket))
        
        if additional_context:
            context_parts.append(additional_context)
        
        # Get conversation history for this ticket
        if ticket:
            history = self.message_bus.get_conversation_context(ticket.id)
            if history and "Keine vorherigen" not in history:
                context_parts.append(f"## Bisherige Kommunikation\n{history}")
        
        # Combine context with user message
        full_message = user_message
        if context_parts:
            full_message = "\n\n".join(context_parts) + "\n\n" + user_message
        
        messages.append({"role": "user", "content": full_message})
        
        # Call LLM
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = await self.client.chat.completions.create(**kwargs)
        
        return response.choices[0].message.content

    async def _call_llm_json(
        self,
        user_message: str,
        ticket: Optional[Ticket] = None,
        additional_context: Optional[str] = None,
    ) -> dict:
        """Call LLM and expect JSON response."""
        response = await self._call_llm(
            user_message=user_message + "\n\nAntworte ausschließlich mit validem JSON.",
            ticket=ticket,
            additional_context=additional_context,
        )
        
        # Clean response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        return json.loads(response.strip())

    async def _call_llm_with_tools(
        self,
        user_message: str,
        ticket: Optional[Ticket] = None,
        additional_context: Optional[str] = None,
        max_tool_calls: int = 10,
    ) -> tuple[str, list[dict]]:
        """
        Call LLM with tool support (function calling).
        
        Returns:
            Tuple of (final_response, tool_results)
        """
        if not self.tools:
            response = await self._call_llm(user_message, ticket, additional_context)
            return response, []
        
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Build context
        context_parts = []
        if ticket:
            context_parts.append(self._format_ticket_context(ticket))
        if additional_context:
            context_parts.append(additional_context)
        if ticket:
            history = self.message_bus.get_conversation_context(ticket.id)
            if history and "Keine vorherigen" not in history:
                context_parts.append(f"## Bisherige Kommunikation\n{history}")
        
        full_message = user_message
        if context_parts:
            full_message = "\n\n".join(context_parts) + "\n\n" + user_message
        
        messages.append({"role": "user", "content": full_message})
        
        tool_schemas = self.tools.get_schemas()
        tool_results = []
        
        for _ in range(max_tool_calls):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                tools=tool_schemas,
                tool_choice="auto",
            )
            
            assistant_message = response.choices[0].message
            messages.append(assistant_message)
            
            # Check if we're done (no tool calls)
            if not assistant_message.tool_calls:
                return assistant_message.content or "", tool_results
            
            # Execute tool calls with retry logic
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                tool = self.tools.get(tool_name)
                if tool:
                    # Validate arguments before execution
                    valid, validation_error = tool.validate_params(**tool_args)
                    if not valid:
                        from tools.base import ToolResultStatus
                        result = ToolResult(
                            status=ToolResultStatus.ERROR,
                            output=None,
                            error=f"Ungültige Argumente: {validation_error}",
                        )
                        tool_results.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": result.to_context(),
                            "success": False,
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result.to_context(),
                        })
                        continue  # Skip to next tool call
                    
                    # Retry logic: up to 2 retries on failure
                    max_retries = 2
                    result = None
                    last_error = None
                    
                    # Log tool call
                    self.log.tool_call(tool_name, tool_args)
                    
                    for attempt in range(max_retries + 1):
                        try:
                            result = await tool.execute(**tool_args)
                            if result.success:
                                self.log.tool_result(tool_name, True, str(result.output)[:50] if result.output else "")
                                break
                            last_error = result.error
                            if attempt < max_retries:
                                self.log.tool_retry(
                                    tool_name,
                                    attempt + 1,
                                    max_retries + 1,
                                    result.error or "Unbekannter Fehler",
                                )
                        except Exception as e:
                            last_error = str(e)
                            if attempt < max_retries:
                                self.log.tool_retry(
                                    tool_name,
                                    attempt + 1,
                                    max_retries + 1,
                                    str(e),
                                )
                            else:
                                # Create error result on final failure
                                from tools.base import ToolResultStatus
                                result = ToolResult(
                                    status=ToolResultStatus.ERROR,
                                    output=None,
                                    error=f"CRITICAL_FAILURE: Tool '{tool_name}' failed after {max_retries + 1} attempts. Error: {last_error}\nDO NOT RETRY. Report this failure immediately to the user.",
                                )
                    
                    # Log final result if failed after retries
                    if result and not result.success:
                        self.log.tool_result(tool_name, False, result.error or "")
                    
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result.to_context(),
                        "success": result.success,
                        "retries": attempt if result else 0,
                    })
                    result_content = result.to_context()
                else:
                    result_content = f"Tool '{tool_name}' nicht gefunden."
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result_content,
                        "success": False,
                    })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content,
                })
        
        # Max iterations reached
        return "Max tool iterations erreicht.", tool_results

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a specific tool directly."""
        from tools.base import ToolResultStatus
        
        if not self.tools:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error="Keine Tools verfügbar.",
            )
        
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Tool '{tool_name}' nicht gefunden.",
            )
        
        return await tool.execute(**kwargs)

    def _format_ticket_context(self, ticket: Ticket) -> str:
        """Format ticket for LLM context."""
        parts = [
            f"## Ticket: {ticket.id}",
            f"**Titel:** {ticket.title}",
            f"**Typ:** {ticket.type.value}",
            f"**Status:** {ticket.status.value}",
            f"**Priorität:** {ticket.priority.value}",
            f"\n### Beschreibung\n{ticket.description}",
        ]
        
        if ticket.acceptance_criteria:
            parts.append("\n### Acceptance Criteria")
            for i, ac in enumerate(ticket.acceptance_criteria, 1):
                parts.append(f"{i}. {ac}")
        
        if ticket.user_story:
            parts.append("\n### User Story")
            parts.append(f"Als {ticket.user_story.as_a}")
            parts.append(f"möchte ich {ticket.user_story.i_want}")
            parts.append(f"damit {ticket.user_story.so_that}")
        
        if ticket.technical_context.affected_areas:
            parts.append("\n### Technischer Kontext")
            parts.append(f"**Betroffene Bereiche:** {', '.join(ticket.technical_context.affected_areas)}")
        
        if ticket.technical_context.related_files:
            parts.append("\n**Relevante Dateien:**")
            for rf in ticket.technical_context.related_files:
                parts.append(f"- `{rf.path}`: {rf.reason}")
        
        if ticket.technical_context.implementation_notes:
            parts.append(f"\n**Implementierungshinweise:**\n{ticket.technical_context.implementation_notes}")
        
        return "\n".join(parts)

    async def ask_agent(
        self,
        target_agent: str,
        question: str,
        ticket_id: Optional[str] = None,
    ) -> Optional[str]:
        """Ask another agent a question."""
        response = await self.message_bus.send_direct(
            from_agent=self.name,
            to_agent=target_agent,
            content=question,
            message_type=MessageType.QUESTION,
            ticket_id=ticket_id,
        )
        
        if response and isinstance(response, AgentResponse):
            return response.message
        return None

    async def handoff_to(
        self,
        target_agent: str,
        task_description: str,
        ticket_id: str,
        context: Optional[dict] = None,
    ) -> Optional[AgentResponse]:
        """Hand off a task to another agent."""
        response = await self.message_bus.send_direct(
            from_agent=self.name,
            to_agent=target_agent,
            content=task_description,
            message_type=MessageType.HANDOFF,
            ticket_id=ticket_id,
            context=context or {},
        )
        
        return response if isinstance(response, AgentResponse) else None

    async def broadcast_update(
        self,
        message: str,
        ticket_id: Optional[str] = None,
    ) -> None:
        """Broadcast an update to all agents."""
        await self.message_bus.broadcast(
            from_agent=self.name,
            content=message,
            message_type=MessageType.UPDATE,
            ticket_id=ticket_id,
        )

    async def _ensure_feature_branch(self, branch_name: str) -> bool:
        """
        Stelle sicher, dass der Feature-Branch existiert und aktiv ist.
        
        Versucht zuerst den Branch zu erstellen. Falls er bereits existiert,
        wird automatisch zu diesem gewechselt.
        
        Args:
            branch_name: Name des Feature-Branches
            
        Returns:
            True wenn Branch erstellt oder gewechselt wurde, False bei Fehler.
        """
        if not self.tools:
            return False
        
        git_branch = self.tools.get("git_branch")
        if not git_branch:
            return False
        
        # Versuche Branch zu erstellen
        result = await git_branch.execute(branch_name=branch_name, action="create")
        
        if result.success:
            self.log.info(f"Feature-Branch '{branch_name}' erstellt")
            return True
        
        # Branch existiert bereits → wechseln
        error_str = str(result.error) if result.error else ""
        if "bereits existiert" in error_str or "already exists" in error_str:
            switch_result = await git_branch.execute(branch_name=branch_name, action="switch")
            if switch_result.success:
                self.log.info(f"Zu Branch '{branch_name}' gewechselt")
                return True
        
        self.log.warning(f"Branch-Operation fehlgeschlagen: {result.error}")
        return False

    async def _check_git_status(self) -> dict:
        """
        Check git status before critical operations.
        
        Returns dict with:
        - has_changes: bool
        - staged: list of staged files
        - modified: list of modified files
        - untracked: list of untracked files
        """
        if not self.tools:
            return {"has_changes": False, "error": "Keine Tools verfügbar"}
        
        git_status = self.tools.get("git_status")
        if not git_status:
            return {"has_changes": False, "error": "git_status Tool nicht verfügbar"}
        
        try:
            result = await git_status.execute()
            if result.success and result.output:
                status_text = result.output.get("status", "")
                has_changes = "nothing to commit" not in status_text.lower()
                return {
                    "has_changes": has_changes,
                    "status": status_text,
                    "error": None,
                }
            return {"has_changes": False, "error": result.error}
        except Exception as e:
            logging.error(f"Fehler bei Git-Status-Prüfung: {e}")
            return {"has_changes": False, "error": str(e)}

    async def _rollback_changes(self) -> dict:
        """
        Rollback uncommitted changes using git checkout.
        
        This is a safety mechanism for critical failures.
        Returns dict with success status and message.
        """
        if not self.tools:
            return {"success": False, "message": "Keine Tools verfügbar"}
        
        git_reset = self.tools.get("git_reset")
        git_checkout_file = self.tools.get("git_checkout_file")
        
        results = []
        
        # Try git reset first (unstage all)
        if git_reset:
            try:
                reset_result = await git_reset.execute(mode="mixed", target="HEAD")
                if reset_result.success:
                    results.append("Staging zurückgesetzt")
                    self.log.debug("Git staging zurückgesetzt via git reset --mixed HEAD")
            except Exception as e:
                self.log.warning(f"Git reset fehlgeschlagen: {e}")
        
        # Then try to discard changes via run_command (git checkout .)
        run_command = self.tools.get("run_command")
        if run_command:
            try:
                # Discard all unstaged changes
                checkout_result = await run_command.execute(
                    command="git checkout .",
                    timeout=30,
                )
                if checkout_result.success:
                    results.append("Änderungen verworfen")
                    self.log.debug("Uncommitted changes verworfen via git checkout .")
                else:
                    self.log.warning(f"Git checkout fehlgeschlagen: {checkout_result.error}")
            except Exception as e:
                self.log.warning(f"Git checkout Exception: {e}")
        
        if results:
            return {
                "success": True,
                "message": f"Rollback durchgeführt: {', '.join(results)}",
            }
        
        return {
            "success": False,
            "message": "Kein Rollback-Tool verfügbar",
        }

    async def _safe_execute_with_rollback(
        self,
        operation_name: str,
        operation_func,
        *args,
        **kwargs,
    ) -> tuple[Any, bool]:
        """
        Execute an operation with automatic rollback on critical failure.
        
        Args:
            operation_name: Name for logging
            operation_func: Async function to execute
            *args, **kwargs: Arguments for the operation
            
        Returns:
            Tuple of (result, rollback_performed)
        """
        # Check git status before operation
        pre_status = await self._check_git_status()
        
        try:
            result = await operation_func(*args, **kwargs)
            return result, False
            
        except Exception as e:
            self.log.error(f"Kritischer Fehler bei {operation_name}", exception=e)
            
            # Check if we have new uncommitted changes that should be rolled back
            post_status = await self._check_git_status()
            
            if post_status.get("has_changes") and not pre_status.get("has_changes"):
                self.log.warning(f"Führe Rollback durch nach Fehler in {operation_name}")
                rollback_result = await self._rollback_changes()
                
                if rollback_result["success"]:
                    self.log.info(f"Rollback erfolgreich: {rollback_result['message']}")
                else:
                    self.log.error(f"Rollback fehlgeschlagen: {rollback_result['message']}")
                
                return None, True
            
            # Re-raise if no rollback was needed/possible
            raise
