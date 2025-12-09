"""Product Owner agent - refines requirements and validates delivery."""

from typing import Optional

from .base_agent import BaseAgent
from core.models import (
    AgentMessage,
    AgentResponse,
    TicketStatus,
    UserStory,
)


class ProductOwnerAgent(BaseAgent):
    """
    Product Owner agent responsible for:
    - Refining tickets with acceptance criteria
    - Writing user stories
    - Validating implemented features
    - Prioritizing by business value
    """

    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Process a task assignment."""
        task_type = message.context.get("task_type", "refine")
        
        if task_type == "validate":
            return await self._validate_implementation(message.ticket_id)
        else:
            return await self._refine_ticket(message.ticket_id, message.content)

    async def _refine_ticket(
        self,
        ticket_id: Optional[str],
        additional_context: str = "",
    ) -> AgentResponse:
        """Refine a ticket with acceptance criteria and user story."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="refinement_failed",
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="refinement_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        # Use LLM to generate refinement
        refinement = await self._call_llm_json(
            user_message=f"""
            Verfeinere dieses Ticket als Product Owner.
            
            Erstelle:
            1. Klare, testbare Acceptance Criteria (mindestens 3)
            2. Eine User Story im Format "Als X möchte ich Y, damit Z"
            
            {additional_context}
            
            Antworte mit JSON:
            {{
                "acceptance_criteria": [
                    "Kriterium 1 - muss testbar sein",
                    "Kriterium 2 - muss testbar sein",
                    ...
                ],
                "user_story": {{
                    "as_a": "Rolle des Nutzers",
                    "i_want": "gewünschte Funktionalität",
                    "so_that": "Nutzen/Mehrwert"
                }},
                "refinement_notes": "Zusätzliche Anmerkungen für das Team"
            }}
            """,
            ticket=ticket,
        )
        
        # Update ticket
        ticket.acceptance_criteria = refinement.get("acceptance_criteria", [])
        
        if "user_story" in refinement:
            us = refinement["user_story"]
            ticket.user_story = UserStory(
                as_a=us.get("as_a", ""),
                i_want=us.get("i_want", ""),
                so_that=us.get("so_that", ""),
            )
        
        # Add comment
        notes = refinement.get("refinement_notes", "")
        ticket.add_comment(
            self.name,
            f"Refinement abgeschlossen. {notes}"
        )
        
        # Update status
        ticket.status = TicketStatus.REFINED
        await self.backlog.save_ticket(ticket)
        
        # Hand off to architect for technical analysis
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="ticket_refined",
            result={
                "acceptance_criteria": ticket.acceptance_criteria,
                "user_story": ticket.user_story.model_dump() if ticket.user_story else None,
            },
            next_agent="architect",
            message=f"Ticket {ticket_id} refined. Übergabe an Architect für technische Analyse.",
        )

    async def _read_implementation_files(self, ticket) -> str:
        """Read source files related to the ticket implementation."""
        file_contents = []
        
        # Get files from technical context
        related_files = []
        if ticket.technical_context and ticket.technical_context.related_files:
            related_files = [f.path for f in ticket.technical_context.related_files]
        
        # Add common implementation files
        common_files = ["main.py", "app.py", "index.py", "server.py"]
        for f in common_files:
            if f not in related_files:
                related_files.append(f)
        
        # Also check for test files
        test_patterns = ["tests/", "test_"]
        
        if not self.tools:
            return "Keine Tools verfügbar zum Lesen der Dateien."
        
        read_file = self.tools.get("read_file")
        find_files = self.tools.get("find_files")
        
        # Find test files
        if find_files:
            try:
                result = await find_files.execute(path=".", pattern="test*.py")
                if result.success and result.output:
                    for line in str(result.output).split("\n"):
                        if line.strip() and line.strip().endswith(".py"):
                            # Extract file path from output
                            path = line.strip().replace("📄 ", "").split(" ")[0]
                            if path not in related_files:
                                related_files.append(path)
            except Exception:
                pass
        
        # Read each file
        if read_file:
            for file_path in related_files[:10]:  # Limit to 10 files
                try:
                    result = await read_file.execute(path=file_path)
                    if result.success and result.output:
                        content = str(result.output)[:3000]  # Limit content size
                        file_contents.append(f"### {file_path}\n```\n{content}\n```")
                except Exception:
                    pass
        
        if not file_contents:
            return "Keine Implementierungsdateien gefunden."
        
        return "\n\n".join(file_contents)

    async def _run_tests_for_validation(self) -> str:
        """Run tests and return results for validation."""
        if not self.tools:
            return "Keine Tools verfügbar zum Ausführen der Tests."
        
        run_command = self.tools.get("run_command")
        if not run_command:
            return "run_command Tool nicht verfügbar."
        
        try:
            # Run pytest
            result = await run_command.execute(
                command="pytest -v --tb=short",
                cwd=".",
                timeout=120,
            )
            
            if result.success:
                output = str(result.output)[:2000]
                return f"✅ Tests erfolgreich:\n{output}"
            else:
                output = str(result.output)[:2000] if result.output else ""
                error = result.error or ""
                return f"⚠️ Tests:\n{output}\n{error}"
        except Exception as e:
            return f"Fehler beim Ausführen der Tests: {e}"

    async def _validate_implementation(self, ticket_id: Optional[str]) -> AgentResponse:
        """Validate that implementation meets acceptance criteria."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="validation_failed",
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="validation_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        if ticket.status != TicketStatus.REVIEW:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="validation_failed",
                message=f"Ticket {ticket_id} ist nicht im Review-Status.",
            )
        
        # Get implementation details
        implementation_info = {
            "commits": ticket.implementation.commits,
            "subtasks": [
                {"id": st.id, "description": st.description, "status": st.status.value}
                for st in ticket.implementation.subtasks
            ],
        }
        
        # Read actual source files for validation
        file_contents = await self._read_implementation_files(ticket)
        
        # Run tests if available
        test_results = await self._run_tests_for_validation()
        
        # Get conversation history for context
        conversation = self.message_bus.get_conversation_context(ticket_id, limit=10)
        
        # Use LLM to validate
        validation = await self._call_llm_json(
            user_message=f"""
            Validiere die Implementierung gegen die Acceptance Criteria.
            
            ## Acceptance Criteria
            {ticket.acceptance_criteria}
            
            ## Implementierungsdetails
            {implementation_info}
            
            ## Quellcode der Implementierung
            {file_contents}
            
            ## Test-Ergebnisse
            {test_results}
            
            ## Kommunikationsverlauf (Kurzfassung)
            {conversation[:2000] if conversation else "Keine Konversation verfügbar"}
            
            WICHTIG: Bewerte die Implementierung anhand des tatsächlichen Quellcodes und der Testergebnisse.
            Wenn Tests erfolgreich sind und der Code die Kriterien erfüllt, ist die Validation bestanden.
            
            Prüfe jedes Acceptance Criterion und bewerte:
            
            Antworte mit JSON:
            {{
                "validation_results": [
                    {{
                        "criterion": "Das geprüfte Kriterium",
                        "passed": true/false,
                        "evidence": "Nachweis/Begründung"
                    }},
                    ...
                ],
                "overall_passed": true/false,
                "feedback": "Zusammenfassendes Feedback",
                "issues": ["Issue 1", "Issue 2"] // nur wenn overall_passed = false
            }}
            """,
            ticket=ticket,
        )
        
        overall_passed = validation.get("overall_passed", False)
        
        if overall_passed:
            ticket.status = TicketStatus.DONE
            ticket.add_comment(self.name, "✅ Alle Acceptance Criteria erfüllt. Ticket abgeschlossen.")
        else:
            ticket.status = TicketStatus.IN_PROGRESS
            issues = validation.get("issues", [])
            ticket.add_comment(
                self.name,
                f"❌ Validation fehlgeschlagen. Issues: {', '.join(issues)}"
            )
        
        await self.backlog.save_ticket(ticket)
        
        return AgentResponse(
            success=overall_passed,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="validation_complete",
            result=validation,
            next_agent="scrum_master" if overall_passed else "backend_dev",
            message=validation.get("feedback", ""),
        )

    async def handle_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from other agents."""
        # Check ticket status to determine action
        if message.ticket_id:
            ticket = self.backlog.get_ticket(message.ticket_id)
            if ticket and ticket.status == TicketStatus.REVIEW:
                # Ticket in review from architect → validate
                return await self._validate_implementation(message.ticket_id)
        
        # Fallback to content-based routing
        if "validiere" in message.content.lower() or "prüfe" in message.content.lower():
            return await self._validate_implementation(message.ticket_id)
        else:
            return await self._refine_ticket(message.ticket_id, message.content)
