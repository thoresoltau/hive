"""Backend Developer agent - implements backend code."""

from typing import Optional

from .base_agent import BaseAgent
from core.models import (
    AgentMessage,
    AgentResponse,
    TicketStatus,
    SubtaskStatus,
)


class BackendDevAgent(BaseAgent):
    """
    Backend Developer agent responsible for:
    - Implementing APIs and business logic
    - Writing backend tests
    - Database operations
    - Following architectural guidelines
    """

    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Process a task assignment."""
        task_type = message.context.get("task_type", "implement")
        
        if task_type == "fix":
            return await self._fix_issues(message.ticket_id, message.context.get("issues", []))
        else:
            return await self._implement_ticket(message.ticket_id)

    async def _implement_ticket(self, ticket_id: Optional[str]) -> AgentResponse:
        """Implement the backend portion of a ticket."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="implementation_failed",
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="implementation_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        # Update status
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.implementation.assigned_to = self.name
        await self.backlog.save_ticket(ticket)
        
        # Get subtasks
        subtasks = ticket.implementation.subtasks
        backend_subtasks = [
            st for st in subtasks
            if not any(kw in st.description.lower() for kw in ["frontend", "ui", "component", "styling"])
        ]
        
        # Check if we have tools available for actual implementation
        if self.tools:
            # Use tools to actually implement the code
            response, tool_results = await self._call_llm_with_tools(
                user_message=f"""
                Implementiere die Backend-Komponenten für dieses Ticket.
                
                ## Zu implementierende Subtasks
                {[st.model_dump() for st in backend_subtasks]}
                
                ## Technischer Kontext
                - Betroffene Bereiche: {ticket.technical_context.affected_areas}
                - Dependencies: {ticket.technical_context.dependencies}
                - Hinweise: {ticket.technical_context.implementation_notes}
                
                Du hast Zugriff auf File-Tools. Nutze sie um:
                1. Zuerst die Projektstruktur zu erkunden (list_directory, find_files)
                2. Relevante existierende Dateien zu lesen (read_file)
                3. Neue Dateien zu erstellen (write_file)
                4. Existierende Dateien zu bearbeiten (edit_file)
                
                Implementiere den Code vollständig und lauffähig.
                Erstelle auch entsprechende Tests.
                
                Fasse am Ende zusammen, was du implementiert hast.
                """,
                ticket=ticket,
            )
            
            # Count successful file operations
            files_created = sum(1 for r in tool_results if r["tool"] == "write_file" and r["success"])
            files_edited = sum(1 for r in tool_results if r["tool"] == "edit_file" and r["success"])
            
            # Run tests after implementation
            test_result = await self._run_tests()
            
            implementation = {
                "summary": response,
                "tool_results": tool_results,
                "files_created": files_created,
                "files_edited": files_edited,
                "tests": test_result,
            }
            
            # Update subtask status
            for subtask in backend_subtasks:
                subtask.status = SubtaskStatus.DONE
            
            # Add implementation comment
            test_status = "✅ Tests bestanden" if test_result.get("passed", False) else "⚠️ Tests fehlgeschlagen"
            ticket.add_comment(
                self.name,
                f"Backend-Implementierung abgeschlossen. "
                f"{files_created} neue Dateien, {files_edited} bearbeitete Dateien. {test_status}"
            )
        else:
            # Fallback: Only generate plan without actual file operations
            implementation = await self._call_llm_json(
                user_message=f"""
                Erstelle einen Implementierungsplan für die Backend-Komponenten.
                
                ## Zu implementierende Subtasks
                {[st.model_dump() for st in backend_subtasks]}
                
                ## Technischer Kontext
                - Betroffene Bereiche: {ticket.technical_context.affected_areas}
                - Dependencies: {ticket.technical_context.dependencies}
                - Hinweise: {ticket.technical_context.implementation_notes}
                
                Antworte mit JSON:
                {{
                    "files_to_create": [
                        {{"path": "src/...", "purpose": "...", "code": "vollständiger Code"}}
                    ],
                    "files_to_modify": [
                        {{"path": "src/...", "changes": "..."}}
                    ],
                    "implementation_summary": "..."
                }}
                """,
                ticket=ticket,
            )
            
            ticket.add_comment(
                self.name,
                f"Implementierungsplan erstellt (ohne Tools). "
                f"{len(implementation.get('files_to_create', []))} Dateien geplant."
            )
        
        await self.backlog.save_ticket(ticket)
        
        # Check if frontend work is needed
        frontend_subtasks = [st for st in subtasks if st not in backend_subtasks]
        
        if frontend_subtasks:
            return AgentResponse(
                success=True,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="backend_implementation_complete",
                result=implementation,
                next_agent="frontend_dev",
                message=f"Backend fertig. {len(frontend_subtasks)} Frontend-Subtasks verbleiben.",
            )
        else:
            ticket.status = TicketStatus.REVIEW
            await self.backlog.save_ticket(ticket)
            
            return AgentResponse(
                success=True,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="implementation_complete",
                result=implementation,
                next_agent="architect",
                message="Implementierung abgeschlossen. Bereit für Code-Review.",
            )

    async def _fix_issues(
        self,
        ticket_id: Optional[str],
        issues: list[str],
    ) -> AgentResponse:
        """Fix issues identified in code review."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="fix_failed",
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="fix_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        if self.tools:
            # Use tools to fix issues
            response, tool_results = await self._call_llm_with_tools(
                user_message=f"""
                Behebe die folgenden Issues aus dem Code-Review:
                
                ## Issues
                {issues}
                
                Nutze die File-Tools um:
                1. Die betroffenen Dateien zu lesen (read_file)
                2. Die Probleme zu beheben (edit_file)
                
                Fasse am Ende zusammen, welche Fixes du vorgenommen hast.
                """,
                ticket=ticket,
            )
            
            fixes_made = sum(1 for r in tool_results if r["tool"] == "edit_file" and r["success"])
            all_fixed = fixes_made > 0
            
            fixes = {
                "summary": response,
                "tool_results": tool_results,
                "fixes_made": fixes_made,
                "all_fixed": all_fixed,
            }
        else:
            # Fallback without tools
            fixes = await self._call_llm_json(
                user_message=f"""
                Beschreibe wie du die folgenden Issues beheben würdest:
                
                ## Issues
                {issues}
                
                Antworte mit JSON:
                {{
                    "fixes": [{{"issue": "...", "fix": "...", "file": "..."}}],
                    "all_fixed": true/false
                }}
                """,
                ticket=ticket,
            )
        
        if fixes.get("all_fixed", False):
            ticket.add_comment(self.name, "Alle Review-Issues behoben.")
            ticket.status = TicketStatus.REVIEW
        else:
            ticket.add_comment(self.name, "Issues teilweise behoben.")
        
        await self.backlog.save_ticket(ticket)
        
        return AgentResponse(
            success=fixes.get("all_fixed", False),
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="issues_fixed",
            result=fixes,
            next_agent="architect",
            message="Issues bearbeitet. Erneutes Review erforderlich.",
        )

    async def _run_tests(self) -> dict:
        """Run tests after implementation."""
        if not self.tools:
            return {"passed": False, "skipped": True, "message": "Keine Tools verfügbar"}
        
        run_command = self.tools.get("run_command")
        if not run_command:
            return {"passed": False, "skipped": True, "message": "run_command Tool nicht verfügbar"}
        
        # Try running pytest
        result = await run_command.execute(command="pytest --tb=short -q", timeout=120)
        
        if result.success:
            return {
                "passed": True,
                "skipped": False,
                "output": result.output[:2000] if result.output else "",
                "message": "Alle Tests bestanden",
            }
        elif result.status.value == "partial":
            # Tests ran but some failed
            return {
                "passed": False,
                "skipped": False,
                "output": result.output[:2000] if result.output else "",
                "exit_code": result.metadata.get("exit_code"),
                "message": "Einige Tests fehlgeschlagen",
            }
        else:
            # Could not run tests
            return {
                "passed": False,
                "skipped": True,
                "error": result.error,
                "message": "Tests konnten nicht ausgeführt werden",
            }

    async def handle_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from other agents."""
        if "fix" in message.content.lower() or "behoben" in message.content.lower():
            issues = message.context.get("issues", [])
            return await self._fix_issues(message.ticket_id, issues)
        else:
            return await self._implement_ticket(message.ticket_id)
