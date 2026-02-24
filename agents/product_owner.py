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
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="refinement_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        # Use LLM to generate refinement
        refinement = await self._call_llm_json(
            user_message=f"""
            Refine this ticket as Product Owner.

            IMPORTANT: If this ticket fundamentally changes the project structure or introduces
            important documentation files that other agents should know about, use the
            `update_context` tool to add them to the global memory (e.g. updating the
            `important_files` or `architecture_notes` fields).

            Create:
            1. Clear, testable Acceptance Criteria (at least 3)
            2. A User Story in the format "As a X I want to Y, so that Z"

            CRITICAL: Do NOT invent or hallucinate files (e.g. docs/architektur.md) in your refinement notes or context if they do not explicitly exist.

            {additional_context}

            Answer with JSON:
            {{
                "acceptance_criteria": [
                    "Criteria 1 - must be testable",
                    "Criteria 2 - must be testable",
                    ...
                ],
                "user_story": {{
                    "as_a": "User role",
                    "i_want": "desired functionality",
                    "so_that": "Benefit/Value"
                }},
                "refinement_notes": "Additional notes for the team",
                "context_updates": {{
                    "important_files": [],
                    "architecture_notes": ""
                }} // Optional: populate if you need to update global context
            }}
            """,
            ticket=ticket,
        )

        # Update context if requested
        context_updates = refinement.get("context_updates")
        if context_updates and self.tools and "update_context" in self.tools:
            try:
                # Only pass non-empty values to avoid wiping out existing
                updates_to_apply = {k: v for k, v in context_updates.items() if v}
                if updates_to_apply:
                    await self.tools["update_context"].execute(**updates_to_apply)
            except Exception as e:
                self.log.error(f"Failed to apply context updates: {e}")

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
            f"Refinement completed. {notes}"
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
            message=f"Ticket {ticket_id} refined. Handover to Architect for technical analysis.",
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

        if not self.tools:
            return "No tools available to read files."

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
            return "No implementation files found."

        return "\n\n".join(file_contents)

    async def _run_tests_for_validation(self) -> str:
        """Run tests and return results for validation."""
        if not self.tools:
            return "No tools available to run the tests."

        run_command = self.tools.get("run_command")
        if not run_command:
            return "run_command tool not available."

        # Get configured or auto-detected test commands
        test_commands = await self._get_test_commands()

        commands_to_run = list(test_commands.values())
        if not commands_to_run:
            return {"passed": False, "error": "No test commands found"}

        try:
            all_passed = True
            outputs = []

            for cmd in commands_to_run:
                # Run detected test command
                result = await run_command.execute(
                    command=cmd,
                    cwd=".",
                    timeout=120,
                )
                out_str = result.output[:2000] if result.output else ""
                outputs.append(f"--- Command: {cmd} ---\n{out_str}")

                if not result.success:
                    all_passed = False

            full_output = "\n\n".join(outputs)

            if all_passed:
                return f"✅ All tests successful:\n{full_output}"
            else:
                return f"⚠️ Some tests failed:\n{full_output}"
        except Exception as e:
            return f"❌ Error executing tests: {str(e)}"

    async def _validate_implementation(self, ticket_id: Optional[str]) -> AgentResponse:
        """Validate that implementation meets acceptance criteria."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="validation_failed",
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="validation_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        if ticket.status != TicketStatus.REVIEW:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="validation_failed",
                message=f"Ticket {ticket_id} is not in review status.",
            )

        # Get implementation details
        implementation_info = {
            "commits": ticket.implementation.commits,
            "subtasks": [
                {"id": st.id, "description": st.description, "status": st.status.value}
                for st in ticket.implementation.subtasks
            ],
        }

        # Ensure we are on the correct feature branch before validating code
        if getattr(ticket, 'implementation', None) and getattr(ticket.implementation, 'branch', None):
            await self._ensure_feature_branch(ticket.implementation.branch)

        # Read actual source files for validation
        file_contents = await self._read_implementation_files(ticket)

        # Run tests if available
        test_results = await self._run_tests_for_validation()

        # Get conversation history for context
        conversation = self.message_bus.get_conversation_context(ticket_id, limit=10)

        # Use LLM to validate
        validation = await self._call_llm_json(
            user_message=f"""
            Validate the implementation against the Acceptance Criteria.

            ## Acceptance Criteria
            {ticket.acceptance_criteria}

            ## Implementation details
            {implementation_info}

            ## Implementation source code
            {file_contents}

            ## Test results
            {test_results}

            ## Communication history (summary)
            {conversation[:2000] if conversation else "No conversation available"}

            IMPORTANT: Evaluate the implementation based on the actual source code and test results.
            If tests are successful and code meets criteria, the validation is passed.

            Check each acceptance criterion and evaluate:

            Answer with JSON:
            {{
                "validation_results": [
                    {{
                        "criterion": "The tested criterion",
                        "passed": true/false,
                        "evidence": "Evidence/reasoning"
                    }},
                    ...
                ],
                "overall_passed": true/false,
                "feedback": "Summarizing feedback",
                "issues": ["Issue 1", "Issue 2"] // only if overall_passed = false
            }}
            """,
            ticket=ticket,
        )

        overall_passed = validation.get("overall_passed", False)

        if overall_passed:
            ticket.status = TicketStatus.DONE
            ticket.add_comment(self.name, "✅ All acceptance criteria met. Ticket completed.")
        else:
            ticket.status = TicketStatus.IN_PROGRESS
            issues = validation.get("issues", [])
            ticket.add_comment(
                self.name,
                f"❌ Validation failed. Issues: {', '.join(issues)}"
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
        if "validate" in message.content.lower() or "check" in message.content.lower():
            return await self._validate_implementation(message.ticket_id)
        else:
            return await self._refine_ticket(message.ticket_id, message.content)
