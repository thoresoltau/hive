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
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="analysis_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
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
            
            Erstelle:
            1. Liste der betroffenen Bereiche
            2. Benötigte Dependencies
            3. Relevante existierende Dateien mit Begründung
            4. Implementierungshinweise
            5. Subtasks für die Entwickler
            6. Komplexitätsschätzung
            
            Antworte mit JSON:
            {{
                "affected_areas": ["area1", "area2"],
                "dependencies": ["dep1", "dep2"],
                "related_files": [
                    {{"path": "src/...", "reason": "Begründung"}},
                    ...
                ],
                "implementation_notes": "Detaillierte technische Hinweise",
                "subtasks": [
                    {{"id": "001-1", "description": "Subtask Beschreibung"}},
                    ...
                ],
                "complexity": "low|medium|high",
                "story_points": 1-13,
                "risks": ["Risiko 1", "Risiko 2"],
                "architectural_notes": "Wichtige Architektur-Entscheidungen"
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
        arch_notes = analysis.get("architectural_notes", "")
        comment = f"Technische Analyse abgeschlossen. Komplexität: {analysis.get('complexity')}."
        if risks:
            comment += f" Risiken: {', '.join(risks)}."
        if arch_notes:
            comment += f" {arch_notes}"
        ticket.add_comment(self.name, comment)
        
        # Update status to planned
        ticket.status = TicketStatus.PLANNED
        await self.backlog.save_ticket(ticket)
        
        # Determine next agent based on affected areas
        next_agent = self._determine_developer(analysis.get("affected_areas", []))
        
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="technical_analysis_complete",
            result=analysis,
            next_agent=next_agent,
            message=f"Technische Analyse für {ticket_id} abgeschlossen. Empfohlener Entwickler: {next_agent}",
        )

    async def _review_implementation(self, ticket_id: Optional[str]) -> AgentResponse:
        """Review implemented code for quality and architecture compliance."""
        if not ticket_id:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="review_failed",
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="review_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        # Get implementation details
        implementation = ticket.implementation
        related_files = ticket.technical_context.related_files
        
        # Use tools to get actual code content for review
        if self.tools:
            # Step 1: Get git diff to see what changed
            # Step 2: Read the actual changed/created files
            # Step 3: Review based on real code
            
            review_response, tool_results = await self._call_llm_with_tools(
                user_message=f"""
                Führe ein ECHTES Code-Review für dieses Ticket durch.
                
                ## Implementierungsdetails
                - Branch: {implementation.branch}
                - Commits: {implementation.commits}
                - Subtasks: {[st.model_dump() for st in implementation.subtasks]}
                - Relevante Dateien: {[rf.path for rf in related_files]}
                
                ## Deine Aufgabe:
                1. Nutze git_diff um die Änderungen zu sehen
                2. Nutze read_file um die geänderten Dateien zu lesen
                3. Prüfe den CODE auf:
                   - Korrektheit der Implementierung
                   - Code-Qualität und Lesbarkeit
                   - Best Practices (Naming, Struktur, etc.)
                   - Potenzielle Bugs oder Security-Issues
                   - Vollständigkeit (erfüllt die Acceptance Criteria?)
                
                ## Am Ende:
                Gib dein Review-Ergebnis als JSON zurück:
                {{
                    "approved": true/false,
                    "quality_score": 1-10,
                    "findings": [
                        {{"severity": "info|warning|error", "message": "...", "file": "...", "line": null}}
                    ],
                    "suggestions": ["..."],
                    "summary": "Zusammenfassung"
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
                    Basierend auf deinem Code-Review, gib das Ergebnis als JSON zurück:
                    
                    Deine bisherige Analyse:
                    {review_response[:2000]}
                    
                    Antworte NUR mit JSON:
                    {{
                        "approved": true/false,
                        "quality_score": 1-10,
                        "findings": [{{"severity": "info|warning|error", "message": "...", "file": "..."}}],
                        "suggestions": ["..."],
                        "summary": "Kurze Zusammenfassung"
                    }}
                    """,
                    ticket=ticket,
                )
            else:
                # No files read - cannot properly review
                review = {
                    "approved": False,
                    "quality_score": 5,
                    "findings": [{"severity": "warning", "message": "Keine Dateien gelesen", "file": None}],
                    "suggestions": ["Relevante Dateien müssen gelesen werden"],
                    "summary": "Review konnte nicht vollständig durchgeführt werden",
                }
        else:
            # Fallback without tools: review based on metadata only
            review = await self._call_llm_json(
                user_message=f"""
                Führe ein Code-Review für dieses Ticket durch (ohne Datei-Zugriff).
                
                ## Implementierungsdetails
                - Branch: {implementation.branch}
                - Commits: {implementation.commits}
                - Subtasks: {[st.model_dump() for st in implementation.subtasks]}
                
                Antworte mit JSON:
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
            ticket.add_comment(self.name, f"✅ Code-Review bestanden. Score: {review.get('quality_score')}/10")
        else:
            findings = review.get("findings", [])
            errors = [f for f in findings if f.get("severity") == "error"]
            ticket.add_comment(
                self.name,
                f"❌ Code-Review: {len(errors)} Fehler gefunden. Nacharbeit erforderlich."
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
                message="Keine Ticket-ID angegeben.",
            )
        
        ticket = self.backlog.get_ticket(ticket_id)
        if not ticket:
            return AgentResponse(
                success=False,
                agent=self.name,
                ticket_id=ticket_id,
                action_taken="estimation_failed",
                message=f"Ticket {ticket_id} nicht gefunden.",
            )
        
        estimation = await self._call_llm_json(
            user_message=f"""
            Schätze die Komplexität und den Aufwand für dieses Ticket.
            
            Berücksichtige:
            - Akzeptanzkriterien
            - Technischen Kontext
            - Potenzielle Risiken
            
            Antworte mit JSON:
            {{
                "complexity": "low|medium|high",
                "story_points": 1-13,
                "reasoning": "Begründung der Schätzung",
                "confidence": "low|medium|high"
            }}
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
            message=f"Schätzung: {estimation.get('story_points')} SP, {estimation.get('complexity')} Komplexität",
        )

    async def _get_codebase_structure(self) -> str:
        """Get codebase structure for context."""
        if not self.codebase_path or not self.codebase_path.exists():
            return "Keine Codebase verfügbar."
        
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
        elif "schätz" in message.content.lower() or "estimate" in message.content.lower():
            return await self._estimate_ticket(message.ticket_id)
        else:
            return await self._analyze_and_plan(message.ticket_id, message.content)
