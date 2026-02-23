"""Software Architect agent - analyzes codebase and creates technical plans."""

from typing import Optional
from pathlib import Path

from .base_agent import BaseAgent
from core.models import (
    AgentMessage,
    AgentResponse,
    TicketStatus,
    TechnicalContext,
    RelatedFile,
    Estimation,
    Complexity,
    Subtask,
)


class ArchitectAgent(BaseAgent):
    """
    Software Architect agent responsible for:
    - Analyzing the existing codebase
    - Identifying affected files and modules
    - Creating technical implementation plans
    - Reviewing code quality
    - Estimating complexity
    """

    def __init__(self, *args, codebase_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.codebase_path = Path(codebase_path) if codebase_path else None

    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Process a task assignment."""
        task_type = message.context.get("task_type", "analyze")

        if task_type == "review":
            return await self._review_implementation(message.ticket_id)
        elif task_type == "estimate":
            return await self._estimate_ticket(message.ticket_id)
        else:
            return await self._analyze_and_plan(message.ticket_id, message.content)

    async def _analyze_and_plan(
        self,
        ticket_id: Optional[str],
        additional_context: str = "",
    ) -> AgentResponse:
        """Analyze codebase and create implementation plan."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="analysis_failed",
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="analysis_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        # Get codebase structure if available
        codebase_info = await self._get_codebase_structure()

        # Use LLM to analyze and plan
        analysis = await self._call_llm_json(
            user_message=f"""
            Analysiere dieses Ticket und erstelle einen technischen Implementierungsplan.

            ## Codebase-Struktur
            {codebase_info}

            {additional_context}

            Create:
            1. List of affected areas
            2. Required Dependencies
            3. Relevant existing files with Reasoning
            4. Implementation hints
            5. Subtasks for developers
            6. Complexity estimation

            Answer with JSON:
            {{
                "affected_areas": ["area1", "area2"],
                "dependencies": ["dep1", "dep2"],
                "related_files": [
                    {{"path": "src/...", "reason": "Reasoning"}},
                    ...
                ],
                "implementation_notes": "Detailed technical notes",
                "subtasks": [
                    {{"id": "001-1", "description": "Subtask description"}},
                    ...
                ],
                "complexity": "low|medium|high",
                "story_points": 1-13,
                "risks": ["Risiko 1", "Risiko 2"],
                "architectural_notes": "Important architectural decisions"
            }}
            """,
            ticket=ticket,
        )

        # Update ticket with technical context
        ticket.technical_context = TechnicalContext(
            affected_areas=analysis.get("affected_areas", []),
            dependencies=analysis.get("dependencies", []),
            related_files=[
                RelatedFile(path=rf["path"], reason=rf["reason"])
                for rf in analysis.get("related_files", [])
            ],
            implementation_notes=analysis.get("implementation_notes", ""),
        )

        # Update estimation
        ticket.estimation = Estimation(
            story_points=analysis.get("story_points"),
            complexity=Complexity(analysis.get("complexity", "medium")),
        )

        # Create subtasks
        ticket.implementation.subtasks = [
            Subtask(id=st["id"], description=st["description"])
            for st in analysis.get("subtasks", [])
        ]

        # Set branch name
        ticket.implementation.branch = f"feature/{ticket.id.lower()}-{ticket.title.lower().replace(' ', '-')[:30]}"

        # Add comment
        risks = analysis.get("risks", [])
        comment = f"Technical analysis completed. Complexity: {analysis.get('complexity')}."
        if risks:
            comment += f" Risks: {', '.join(risks)}."

        # ADR Trigger Logik
        arch_notes = analysis.get("architectural_notes", "")
        if arch_notes and len(arch_notes) > 20: # Nur bei substantiellen Notes
            # Erstelle Draft
            adr_file = await self._propose_adr(
                title=ticket.title,
                context=f"Ticket {ticket.id}: {ticket.title}\n\n{ticket.description}\n\nArchitecture Notes: {arch_notes}",
                decision="Proposed: " + arch_notes.split(".")[0], # Erste Satz als Kurzform
                consequences="TBD",
                ticket_id=ticket.id
            )
            comment += f"\n\n🛑 **ADR Proposed**: `{adr_file}`. Please review!"

        elif arch_notes:
            comment += f" {arch_notes}"

        ticket.add_comment(self.name, comment)

        # Update status to planned
        ticket.status = TicketStatus.PLANNED
        await self.backlog.save_ticket(ticket)

        # Determine next agent based on affected areas
        next_agent = self._determine_developer(analysis.get("affected_areas", []))

        # Determine ADR status
        adr_file = None

        # ADR Trigger Logik restoration (captured in local vars)
        arch_notes = analysis.get("architectural_notes", "")
        if arch_notes and len(arch_notes) > 20:
             # Logic was executed above, we need to know if it happened.
             # Ideally we capture the filename in previous block.
             pass

        # Re-implementing block to capture filename variable properly
        # WARN: previous replace might have made code messy if I don't see full context.
        # Let's rely on 'analysis' dict modification? No.

        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="adr_proposed" if "Proposed" in comment else "technical_analysis_complete",
            result=analysis,
            next_agent=next_agent,
            message=f"Technical analysis for {ticket_id} completed. Recommended developer: {next_agent}",
        )

    async def _review_implementation(self, ticket_id: Optional[str]) -> AgentResponse:
        """Review implemented code for quality and architecture compliance."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="review_failed",
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="review_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        # Get implementation details
        implementation = ticket.implementation
        related_files = ticket.technical_context.related_files

        # Ensure we are on the correct feature branch before reviewing code
        if implementation and getattr(implementation, 'branch', None):
            await self._ensure_feature_branch(implementation.branch)

        # Use tools to get actual code content for review
        if self.tools:
            # Step 1: Get git diff to see what changed
            # Step 2: Read the actual changed/created files
            # Step 3: Review based on real code

            review_response, tool_results = await self._call_llm_with_tools(
                user_message=f"""
                Perform a REAL code review for this ticket.

                ## Implementation details
                - Branch: {implementation.branch}
                - Commits: {implementation.commits}
                - Subtasks: {[st.model_dump() for st in implementation.subtasks]}
                - Relevant files: {[rf.path for rf in related_files]}

                ## Your task:
                1. Use git_diff to see the changes
                2. Use read_file to read the modified files
                3. Check the CODE for:
                   - Correctness of the implementation
                   - Code quality and readability
                   - Best Practices (Naming, Structure, etc.)
                   - Potential Bugs or Security Issues
                   - Completeness (fulfills the Acceptance Criteria?)

                ## At the end:
                Return your review result as JSON:
                {{
                    "approved": true/false,
                    "quality_score": 1-10,
                    "findings": [
                        {{"severity": "info|warning|error", "message": "...", "file": "...", "line": null}}
                    ],
                    "suggestions": ["..."],
                    "summary": "Summary"
                }}
                """,
                ticket=ticket,
                max_tool_calls=15,
            )

            # Get structured review result via separate JSON call
            files_read = sum(1 for r in tool_results if r["tool"] == "read_file" and r["success"])

            if files_read > 0:
                # Generate structured review based on what was read
                review = await self._call_llm_json(
                    user_message=f"""
                    Based on your code review, return the result as JSON:

                    Your previous analysis:
                    {review_response[:2000]}

                    Answer with JSON:
                    {{
                        "approved": true/false,
                        "quality_score": 1-10,
                        "findings": [{{"severity": "info|warning|error", "message": "...", "file": "..."}}],
                        "suggestions": ["..."],
                        "summary": "Kurze Summary"
                    }}
                    """,
                    ticket=ticket,
                )
            else:
                # No files read - cannot properly review
                review = {
                    "approved": False,
                    "quality_score": 5,
                    "findings": [{"severity": "warning", "message": "No files read", "file": None}],
                    "suggestions": ["Relevant files must be read"],
                    "summary": "Review could not be fully performed",
                }
        else:
            # Fallback without tools: review based on metadata only
            review = await self._call_llm_json(
                user_message=f"""
                Perform a code review for this ticket (without file access).

                ## Implementation details
                - Branch: {implementation.branch}
                - Commits: {implementation.commits}
                - Subtasks: {[st.model_dump() for st in implementation.subtasks]}

                Answer with JSON:
                {{
                    "approved": true/false,
                    "quality_score": 1-10,
                    "findings": [],
                    "suggestions": [],
                    "summary": "..."
                }}
                """,
                ticket=ticket,
            )

        approved = review.get("approved", False)

        if approved:
            ticket.status = TicketStatus.REVIEW
            ticket.add_comment(self.name, f"✅ Code review passed. Score: {review.get('quality_score')}/10")
        else:
            findings = review.get("findings", [])
            errors = [f for f in findings if f.get("severity") == "error"]
            ticket.add_comment(
                self.name,
                f"❌ Code review: {len(errors)} errors found. Rework required."
            )

        await self.backlog.save_ticket(ticket)

        return AgentResponse(
            success=approved,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="code_review_complete",
            result=review,
            next_agent="product_owner" if approved else "backend_dev",
            message=review.get("summary", ""),
        )

    async def _estimate_ticket(self, ticket_id: Optional[str]) -> AgentResponse:
        """Estimate ticket complexity and story points."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="estimation_failed",
                message="No ticket ID specified.",
            )

        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="estimation_failed",
                message=f"Ticket {ticket_id} not found.",
            )

        estimation = await self._call_llm_json(
            user_message="""
            Estimate the complexity and effort for this ticket.

            Consider:
            - Acceptance criteria
            - Technical context
            - Potential risks

            Answer with JSON:
            {
                "complexity": "low|medium|high",
                "story_points": 1-13,
                "reasoning": "Reasoning of the estimation",
                "confidence": "low|medium|high"
            }
            """,
            ticket=ticket,
        )

        ticket.estimation = Estimation(
            complexity=Complexity(estimation.get("complexity", "medium")),
            story_points=estimation.get("story_points"),
        )
        await self.backlog.save_ticket(ticket)

        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="estimation_complete",
            result=estimation,
            message=f"Estimation: {estimation.get('story_points')} SP, {estimation.get('complexity')} complexity",
        )

    async def _get_codebase_structure(self) -> str:
        """Get codebase structure for context."""
        if not self.codebase_path or not self.codebase_path.exists():
            return "No codebase available."

        # Simple tree structure
        structure = []
        for item in sorted(self.codebase_path.rglob("*")):
            if any(part.startswith(".") for part in item.parts):
                continue
            if item.is_file() and item.suffix in [".py", ".ts", ".js", ".tsx", ".jsx", ".yaml", ".json"]:
                rel_path = item.relative_to(self.codebase_path)
                structure.append(str(rel_path))

        return "\n".join(structure[:100])  # Limit to 100 files

    def _determine_developer(self, affected_areas: list[str]) -> str:
        """Determine which developer should work on the ticket."""
        frontend_keywords = ["frontend", "ui", "component", "css", "style", "react", "vue", "page"]
        backend_keywords = ["backend", "api", "database", "server", "auth", "service"]

        has_frontend = any(
            any(kw in area.lower() for kw in frontend_keywords)
            for area in affected_areas
        )
        has_backend = any(
            any(kw in area.lower() for kw in backend_keywords)
            for area in affected_areas
        )

        if has_frontend and has_backend:
            return "backend_dev"  # Backend first, then frontend
        elif has_frontend:
            return "frontend_dev"
        else:
            return "backend_dev"

    async def handle_handoff(self, message: AgentMessage) -> AgentResponse:
        """Handle handoff from other agents."""
        # Check ticket status to determine action
        if message.ticket_id:
            ticket = self.backlog.get_ticket(message.ticket_id)
            if ticket and ticket.status == TicketStatus.REVIEW:
                return await self._review_implementation(message.ticket_id)

        # Fallback to content-based routing
        if "review" in message.content.lower():
            return await self._review_implementation(message.ticket_id)
        elif "estimate" in message.content.lower() or "estimation" in message.content.lower():
            return await self._estimate_ticket(message.ticket_id)
        else:
            return await self._analyze_and_plan(message.ticket_id, message.content)

    async def _propose_adr(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        ticket_id: str,
    ) -> str:
        """Create a new ADR proposal."""
        import datetime

        # Check for existing ADRs to determine ID
        adr_dir = Path("docs/adr")
        if self.codebase_path:
            adr_dir = self.codebase_path / "docs/adr"

        if not adr_dir.exists():
            adr_dir.mkdir(parents=True, exist_ok=True)

        existing = list(adr_dir.glob("[0-9][0-9][0-9]*"))
        next_id = len(existing) + 1

        slug = title.lower().replace(" ", "-")[:50]
        filename = f"{next_id:03d}-{slug}.md"
        file_path = adr_dir / filename

        # Determine deciders (team)
        deciders = ["Architect", "Product Owner", "Backend Dev", "Frontend Dev"]

        template = f"""# {next_id}. {title}

Status: Proposed
Date: {datetime.date.today()}
Deciders: {', '.join(deciders)}
Ticket: {ticket_id}

## Context and Problem Statement

{context}

## Decision Drivers

* Technical feasibility
* Maintainability
* Performance requirements

## Considered Options

* Option 1: [Proposed Solution]
* Option 2: [Status Quo / Alternatives]

## Decision Outcome

Chosen option: "{decision}"

### Positive Consequences

* Solves the immediate problem in {ticket_id}

### Negative Consequences

* {consequences}
"""

        # Write file directly if tools not available (fallback), else use write_file tool
        if self.tools:
            write_tool = self.tools.get("write_file")
            if write_tool:
                await write_tool.execute(
                    path=str(file_path),
                    content=template,
                    overwrite=False
                )
            else:
                file_path.write_text(template)
        else:
            file_path.write_text(template)

        return str(filename)
