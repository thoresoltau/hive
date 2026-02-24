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
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="implementation_failed",
                message=f"Ticket {ticket_id} not found.",
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

        if self.tools:
            # Create feature branch before implementation
            if ticket.implementation.branch:
                await self._ensure_feature_branch(ticket.implementation.branch)

            MAX_ATTEMPTS = 3
            attempt = 1
            all_tool_results = []
            final_response = ""
            files_created = 0
            files_edited = 0
            test_result = {}

            current_prompt = f"""
                Implement the backend components for this ticket.

                ## Subtasks to implement
                {[st.model_dump() for st in backend_subtasks]}

                ## Technical context
                - Affected areas: {ticket.technical_context.affected_areas}
                - Dependencies: {ticket.technical_context.dependencies}
                - Notes: {ticket.technical_context.implementation_notes}

                You have access to file tools. Use them to:
                1. First explore the project structure (list_directory, find_files)
                2. Read relevant existing files (read_file)
                3. Create new files (write_file)
                4. Edit existing files (edit_file)

                Implement the code fully and runnable.
                Create corresponding tests as well.

                Summarize what you implemented at the end.
                """

            while attempt <= MAX_ATTEMPTS:
                # Use tools to actually implement the code
                response, tool_results = await self._call_llm_with_tools(
                    user_message=current_prompt,
                    ticket=ticket,
                )

                final_response = response
                all_tool_results.extend(tool_results)

                # Count successful file operations
                files_created += sum(1 for r in tool_results if r["tool"] == "write_file" and r["success"])
                files_edited += sum(1 for r in tool_results if r["tool"] == "edit_file" and r["success"])

                # Run tests after implementation
                test_result = await self._run_tests()

                # Check outcome
                if test_result.get("passed", False) or test_result.get("skipped", False):
                    break
                else:
                    self.log.info(f"Tests failed on attempt {attempt}. Retrying.")
                    attempt += 1
                    if attempt <= MAX_ATTEMPTS:
                        current_prompt = f"""
                            The tests failed after your previous implementation. Please fix the errors!

                            ## Test Output
                            ```
                            {test_result.get("output", "No output available")}
                            ```

                            Use your file tools (read_file, edit_file) to investigate and fix the issues.
                            Make sure the tests pass. Summarize your fixes at the end.
                            """

            implementation = {
                "summary": final_response,
                "tool_results": all_tool_results,
                "files_created": files_created,
                "files_edited": files_edited,
                "tests": test_result,
            }

            # Update subtask status
            for subtask in backend_subtasks:
                subtask.status = SubtaskStatus.DONE

            # Add implementation comment
            test_status = "✅ Tests passed" if test_result.get("passed", False) else "⚠️ Tests failed"
            ticket.add_comment(
                self.name,
                f"Backend implementation completed. "
                f"{files_created} new files, {files_edited} edited files. {test_status}"
            )
        else:
            # Fallback: Only generate plan without actual file operations
            implementation = await self._call_llm_json(
                user_message=f"""
                Create an implementation plan for the backend components.

                ## Subtasks to implement
                {[st.model_dump() for st in backend_subtasks]}

                ## Technical context
                - Affected areas: {ticket.technical_context.affected_areas}
                - Dependencies: {ticket.technical_context.dependencies}
                - Notes: {ticket.technical_context.implementation_notes}

                Antworte mit JSON:
                {{
                    "files_to_create": [
                        {{"path": "src/...", "purpose": "...", "code": "complete code"}}
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
                f"Implementation plan created (without tools). "
                f"{len(implementation.get('files_to_create', []))} files planned."
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
                message=f"Backend finished. {len(frontend_subtasks)} frontend subtasks remain.",
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
                message="Implementation complete. Ready for code review.",
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
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="fix_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        if self.tools:
            MAX_ATTEMPTS = 3
            attempt = 1
            all_tool_results = []
            final_response = ""
            fixes_made = 0
            test_result = {}

            current_prompt = f"""
                Fix the following issues from code review:

                ## Issues
                {issues}

                Use the File-Tools for:
                1. Read the affected files (read_file)
                2. Fix the issues (edit_file)

                Summarize which fixes you made at the end.
                """

            while attempt <= MAX_ATTEMPTS:
                # Use tools to fix issues
                response, tool_results = await self._call_llm_with_tools(
                    user_message=current_prompt,
                    ticket=ticket,
                )

                final_response = response
                all_tool_results.extend(tool_results)
                current_fixes = sum(1 for r in tool_results if r["tool"] in ["edit_file", "write_file", "run_command"] and r["success"])
                fixes_made += current_fixes

                if current_fixes == 0:
                    self.log.info(f"No changes made on attempt {attempt}. Forcing retry.")
                    attempt += 1
                    if attempt <= MAX_ATTEMPTS:
                        current_prompt = f"""
                            You did not make any successful code changes in the last iteration!
                            You MUST actively use your tools (edit_file, write_file) to fix the listed issues.
                            Do NOT just output text. Apply the fixes to the codebase.
                            """
                    continue

                # Check tests
                test_result = await self._run_tests()
                if test_result.get("passed", False) or test_result.get("skipped", False):
                    break
                else:
                    self.log.info(f"Tests failed during review fixes on attempt {attempt}. Retrying.")
                    attempt += 1
                    if attempt <= MAX_ATTEMPTS:
                        current_prompt = f"""
                            The tests failed after your recent fixes. Please correct the errors!

                            ## Test Output
                            ```
                            {test_result.get("output", "No output available")}
                            ```

                            Use your file tools (read_file, edit_file) to fix the issues so tests pass again.
                            """

            all_fixed = fixes_made > 0

            fixes = {
                "summary": final_response,
                "tool_results": all_tool_results,
                "fixes_made": fixes_made,
                "all_fixed": all_fixed,
            }
        else:
            # Fallback without tools
            fixes = await self._call_llm_json(
                user_message=f"""
                Describe how you would fix the following issues:

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
            ticket.add_comment(self.name, "All review issues fixed.")
            ticket.status = TicketStatus.REVIEW
        else:
            ticket.add_comment(self.name, "Issues partially fixed.")

        await self.backlog.save_ticket(ticket)

        return AgentResponse(
            success=fixes.get("all_fixed", False),
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="issues_fixed",
            result=fixes,
            next_agent="architect",
            message="Issues addressed. Another review required.",
        )

    async def _run_tests(self) -> dict:
        """Run tests after implementation."""
        if not self.tools:
            return {"passed": False, "skipped": True, "message": "No tools available"}

        run_command = self.tools.get("run_command")
        if not run_command:
            return {"passed": False, "skipped": True, "message": "run_command tool not available"}

        # Get configured or auto-detected test commands
        test_commands = await self._get_test_commands()

        # Backend dev tries to run 'backend' tests if specified, otherwise runs all
        commands_to_run = []
        if "backend" in test_commands:
            commands_to_run.append(test_commands["backend"])
        else:
            commands_to_run = list(test_commands.values())

        if not commands_to_run:
            return {"passed": False, "skipped": True, "message": "No test commands found"}

        # Run the commands sequentially
        all_passed = True
        outputs = []
        for cmd in commands_to_run:
            result = await run_command.execute(command=cmd, timeout=120)
            out_str = result.output[:2000] if result.output else ""
            outputs.append(f"--- Command: {cmd} ---\n{out_str}")
            if not result.success:
                all_passed = False

        full_output = "\n\n".join(outputs)

        if all_passed:
            return {
                "passed": True,
                "skipped": False,
                "output": full_output,
                "message": "All tests passed",
            }
        else:
            # Tests ran but some failed
            return {
                "passed": False,
                "skipped": False,
                "output": full_output,
                "message": "Some tests failed",
            }

    async def handle_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from other agents."""
        is_fix = False
        msg_lower = message.content.lower()
        if "fix" in msg_lower or "behoben" in msg_lower or "rework" in msg_lower:
            is_fix = True

        findings = message.context.get("findings", [])
        if findings and not message.context.get("approved", True):
            is_fix = True

        issues = message.context.get("issues", [])
        if not issues and findings:
            issues = [f"[{f.get('severity', 'error').upper()}] {f.get('file', 'Unknown')}: {f.get('message', '')}" for f in findings]

        if is_fix:
            if not issues:
                issues = [message.content]
            return await self._fix_issues(message.ticket_id, issues)
        else:
            return await self._implement_ticket(message.ticket_id)
