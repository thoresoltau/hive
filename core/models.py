"""Pydantic models for tickets and agent communication."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TicketType(str, Enum):
    FEATURE = "feature"
    BUG = "bug"
    REFACTOR = "refactor"
    CHORE = "chore"
    SPIKE = "spike"


class TicketStatus(str, Enum):
    BACKLOG = "backlog"
    REFINED = "refined"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SubtaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


# === Sub-Models ===

class UserStory(BaseModel):
    as_a: str
    i_want: str
    so_that: str


class RelatedFile(BaseModel):
    path: str
    reason: str


class TechnicalContext(BaseModel):
    affected_areas: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    related_files: list[RelatedFile] = Field(default_factory=list)
    implementation_notes: Optional[str] = None


class Estimation(BaseModel):
    story_points: Optional[int] = None
    complexity: Optional[Complexity] = None


class TicketDependencies(BaseModel):
    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)


class Subtask(BaseModel):
    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING


class Implementation(BaseModel):
    assigned_to: Optional[str] = None
    branch: Optional[str] = None
    commits: list[str] = Field(default_factory=list)
    subtasks: list[Subtask] = Field(default_factory=list)


class Comment(BaseModel):
    agent: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str


class Metadata(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "human"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sprint: Optional[int] = None


# === Main Ticket Model ===

class Ticket(BaseModel):
    id: str
    type: TicketType
    title: str
    priority: Priority = Priority.MEDIUM
    status: TicketStatus = TicketStatus.BACKLOG
    
    # Core content
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    user_story: Optional[UserStory] = None
    
    # Technical
    technical_context: TechnicalContext = Field(default_factory=TechnicalContext)
    
    # Planning
    estimation: Estimation = Field(default_factory=Estimation)
    dependencies: TicketDependencies = Field(default_factory=TicketDependencies)
    
    # Implementation tracking
    implementation: Implementation = Field(default_factory=Implementation)
    
    # Communication
    comments: list[Comment] = Field(default_factory=list)
    
    # Meta
    metadata: Metadata = Field(default_factory=Metadata)

    def add_comment(self, agent: str, message: str) -> None:
        """Add a comment from an agent."""
        self.comments.append(Comment(agent=agent, message=message))
        self.metadata.updated_at = datetime.utcnow()

    def is_refined(self) -> bool:
        """Check if ticket has minimum required refinement."""
        return (
            len(self.acceptance_criteria) > 0
            and len(self.technical_context.affected_areas) > 0
        )

    def can_start(self) -> bool:
        """Check if ticket can be started."""
        return (
            self.status == TicketStatus.PLANNED
            and self.is_refined()
            and len(self.dependencies.blocked_by) == 0
        )


# === Agent Communication ===

class MessageType(str, Enum):
    TASK = "task"
    RESPONSE = "response"
    QUESTION = "question"
    UPDATE = "update"
    HANDOFF = "handoff"


class AgentMessage(BaseModel):
    """Message passed between agents."""
    id: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    from_agent: str
    to_agent: str
    message_type: MessageType
    ticket_id: Optional[str] = None
    content: str
    context: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    """Response from an agent after processing."""
    success: bool
    agent: str
    ticket_id: Optional[str] = None
    action_taken: str
    result: dict = Field(default_factory=dict)
    next_agent: Optional[str] = None
    message: Optional[str] = None
