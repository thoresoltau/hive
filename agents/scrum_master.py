"""Scrum Master agent - orchestrates workflow and manages sprint."""

from typing import Optional

from .base_agent import BaseAgent
from core.models import (
    AgentMessage,
    AgentResponse,
    TicketStatus,
    Priority,
)


class ScrumMasterAgent(BaseAgent):
    """
    Scrum Master agent responsible for:
    - Selecting next ticket from backlog
    - Orchestrating the refinement process
    - Managing sprint workflow
    - Identifying and resolving blockers
    """
    
    # Loop detection: track how often each ticket cycles through
    _ticket_cycle_counts: dict[str, int] = {}
    MAX_CYCLES_PER_TICKET = 5  # Maximum cycles before blocking

    async def process_task(self, message: AgentMessage) -> AgentResponse:
        """Process a task assignment."""
        task_type = message.context.get("task_type", "orchestrate")
        
        if task_type == "select_next_ticket":
            return await self._select_next_ticket()
        elif task_type == "start_refinement":
            return await self._start_refinement(message.ticket_id)
        elif task_type == "check_blockers":
            return await self._check_blockers()
        elif task_type == "sprint_planning":
            return await self._run_sprint_planning()
        else:
            return await self._orchestrate_workflow()

    async def _select_next_ticket(self) -> AgentResponse:
        """Select the next ticket to work on."""
        # First check for tickets ready for implementation
        ready_ticket = self.backlog.get_next_ticket_for_work()
        if ready_ticket:
            return AgentResponse(
                success=True,
                agent=self.name,
                ticket_id=ready_ticket.id,
                action_taken="ticket_selected_for_work",
                result={"ticket_id": ready_ticket.id, "status": "ready_for_implementation"},
                next_agent="architect",
                message=f"Ticket {ready_ticket.id} ist bereit für Implementierung.",
            )
        
        # Otherwise, look for tickets needing refinement
        backlog_ticket = self.backlog.get_next_ticket_for_refinement()
        if backlog_ticket:
            return AgentResponse(
                success=True,
                agent=self.name,
                ticket_id=backlog_ticket.id,
                action_taken="ticket_selected_for_refinement",
                result={"ticket_id": backlog_ticket.id, "status": "needs_refinement"},
                next_agent="product_owner",
                message=f"Ticket {backlog_ticket.id} muss refined werden.",
            )
        
        return AgentResponse(
            success=True,
            agent=self.name,
            action_taken="no_tickets_available",
            message="Keine Tickets im Backlog verfügbar.",
        )

    async def _start_refinement(self, ticket_id: Optional[str]) -> AgentResponse:
        """Initiate refinement process for a ticket."""
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
        
        # Hand off to Product Owner for refinement
        ticket.add_comment(
            self.name,
            "Refinement-Prozess gestartet. Übergabe an Product Owner."
        )
        await self.backlog.save_ticket(ticket)
        
        response = await self.handoff_to(
            target_agent="product_owner",
            task_description="Bitte verfeinere dieses Ticket mit Acceptance Criteria und User Story.",
            ticket_id=ticket_id,
        )
        
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket_id,
            action_taken="refinement_started",
            result={"po_response": response.result if response else None},
            next_agent="product_owner",
            message=f"Refinement für {ticket_id} gestartet.",
        )

    async def _check_blockers(self) -> AgentResponse:
        """Check for and report blocked tickets."""
        blocked_tickets = self.backlog.get_tickets_by_status(TicketStatus.BLOCKED)
        
        if not blocked_tickets:
            return AgentResponse(
                success=True,
                agent=self.name,
                action_taken="blocker_check",
                result={"blocked_count": 0},
                message="Keine blockierten Tickets.",
            )
        
        blocker_details = []
        for ticket in blocked_tickets:
            blockers = ticket.dependencies.blocked_by
            blocker_details.append({
                "ticket_id": ticket.id,
                "blocked_by": blockers,
                "title": ticket.title,
            })
        
        # Use LLM to analyze blockers
        analysis = await self._call_llm(
            user_message=f"""
            Analysiere die folgenden Blocker und schlage Lösungen vor:
            
            {blocker_details}
            
            Gib konkrete Handlungsempfehlungen.
            """,
        )
        
        return AgentResponse(
            success=True,
            agent=self.name,
            action_taken="blocker_analysis",
            result={
                "blocked_count": len(blocked_tickets),
                "details": blocker_details,
                "analysis": analysis,
            },
            message=f"{len(blocked_tickets)} blockierte Tickets gefunden.",
        )

    async def _run_sprint_planning(self) -> AgentResponse:
        """Run sprint planning session."""
        # Get refined tickets
        refined_tickets = self.backlog.get_tickets_by_status(TicketStatus.REFINED)
        planned_tickets = self.backlog.get_tickets_by_status(TicketStatus.PLANNED)
        
        available_tickets = refined_tickets + planned_tickets
        
        if not available_tickets:
            return AgentResponse(
                success=False,
                agent=self.name,
                action_taken="sprint_planning_failed",
                message="Keine refined Tickets für Sprint Planning verfügbar.",
            )
        
        # Prepare ticket summaries for LLM
        ticket_summaries = []
        for t in available_tickets:
            ticket_summaries.append({
                "id": t.id,
                "title": t.title,
                "priority": t.priority.value,
                "complexity": t.estimation.complexity.value if t.estimation.complexity else "unknown",
                "story_points": t.estimation.story_points,
                "blocked_by": t.dependencies.blocked_by,
            })
        
        # Ask LLM to prioritize
        planning_result = await self._call_llm_json(
            user_message=f"""
            Sprint Planning: Priorisiere die folgenden Tickets für den nächsten Sprint.
            
            Verfügbare Tickets:
            {ticket_summaries}
            
            Berücksichtige:
            1. Priorität (critical > high > medium > low)
            2. Abhängigkeiten (blocked_by muss leer sein oder bereits geplant)
            3. Komplexität und Story Points
            
            Antworte mit JSON:
            {{
                "sprint_tickets": ["TICKET-ID-1", "TICKET-ID-2", ...],
                "reasoning": "Erklärung der Priorisierung"
            }}
            """,
        )
        
        return AgentResponse(
            success=True,
            agent=self.name,
            action_taken="sprint_planning_complete",
            result=planning_result,
            message=f"Sprint Planning abgeschlossen. {len(planning_result.get('sprint_tickets', []))} Tickets geplant.",
        )

    async def _orchestrate_workflow(self) -> AgentResponse:
        """Main orchestration loop - determine next action."""
        # Get current state
        summary = self.backlog.get_sprint_summary()
        
        # Check for blocked tickets first
        blocked_count = summary["status_breakdown"].get("blocked", 0)
        if blocked_count > 0:
            return await self._check_blockers()
        
        # Check for tickets in REVIEW status - delegate to architect for code review
        review_tickets = self.backlog.get_tickets_by_status(TicketStatus.REVIEW)
        if review_tickets:
            ticket = review_tickets[0]
            
            # Loop detection: check if this ticket has cycled too many times
            if await self._check_and_handle_loop(ticket):
                # Ticket was blocked due to loop, get next ticket
                return await self._select_next_ticket()
            
            return AgentResponse(
                success=True,
                agent=self.name,
                ticket_id=ticket.id,
                action_taken="delegating_to_review",
                result={"ticket_id": ticket.id, "status": "review"},
                next_agent="architect",
                message=f"Ticket {ticket.id} wartet auf Code-Review.",
            )
        
        # Check for tickets in progress - delegate to assigned developer
        in_progress_tickets = self.backlog.get_tickets_by_status(TicketStatus.IN_PROGRESS)
        if in_progress_tickets:
            ticket = in_progress_tickets[0]
            
            # Loop detection for in_progress tickets too
            if await self._check_and_handle_loop(ticket):
                return await self._select_next_ticket()
            
            assigned_to = ticket.implementation.assigned_to
            
            if assigned_to:
                return AgentResponse(
                    success=True,
                    agent=self.name,
                    ticket_id=ticket.id,
                    action_taken="delegating_to_developer",
                    result={"ticket_id": ticket.id, "assigned_to": assigned_to},
                    next_agent=assigned_to,
                    message=f"Ticket {ticket.id} an {assigned_to} delegiert zur Weiterarbeit.",
                )
            else:
                # Ticket in progress but no one assigned - assign to appropriate dev
                return await self._assign_developer(ticket)
        
        # If nothing in progress, select next ticket
        return await self._select_next_ticket()
    
    async def _check_and_handle_loop(self, ticket) -> bool:
        """
        Check if a ticket has cycled too many times and handle it.
        
        Returns True if ticket was blocked due to loop, False otherwise.
        """
        ticket_id = ticket.id
        
        # Increment cycle counter
        if ticket_id not in self._ticket_cycle_counts:
            self._ticket_cycle_counts[ticket_id] = 0
        self._ticket_cycle_counts[ticket_id] += 1
        
        cycle_count = self._ticket_cycle_counts[ticket_id]
        
        if cycle_count > self.MAX_CYCLES_PER_TICKET:
            # Block the ticket due to loop
            self.log.warning(
                f"🔄 Loop erkannt: Ticket {ticket_id} hat {cycle_count} Zyklen durchlaufen. "
                f"Ticket wird blockiert."
            )
            
            ticket.status = TicketStatus.BLOCKED
            ticket.add_comment(
                self.name,
                f"⚠️ Ticket blockiert wegen Endlosschleife ({cycle_count} Zyklen). "
                f"Manuelle Prüfung erforderlich. Letzter Status vor Blockierung: {ticket.status.value}"
            )
            await self.backlog.save_ticket(ticket)
            
            # Reset counter for this ticket
            del self._ticket_cycle_counts[ticket_id]
            
            return True
        
        return False
    
    def reset_cycle_counter(self, ticket_id: str) -> None:
        """Reset the cycle counter for a ticket (e.g., when it's done)."""
        if ticket_id in self._ticket_cycle_counts:
            del self._ticket_cycle_counts[ticket_id]
    
    async def _assign_developer(self, ticket) -> AgentResponse:
        """Assign a developer to an unassigned in-progress ticket."""
        # Determine appropriate developer based on affected areas
        areas = ticket.technical_context.affected_areas
        
        # Simple heuristic: frontend keywords → frontend_dev, else → backend_dev
        frontend_keywords = ["frontend", "ui", "component", "page", "css", "react", "vue"]
        is_frontend = any(
            any(kw in area.lower() for kw in frontend_keywords)
            for area in areas
        )
        
        assigned_to = "frontend_dev" if is_frontend else "backend_dev"
        ticket.implementation.assigned_to = assigned_to
        await self.backlog.save_ticket(ticket)
        
        return AgentResponse(
            success=True,
            agent=self.name,
            ticket_id=ticket.id,
            action_taken="developer_assigned",
            result={"ticket_id": ticket.id, "assigned_to": assigned_to},
            next_agent=assigned_to,
            message=f"Ticket {ticket.id} an {assigned_to} zugewiesen.",
        )
