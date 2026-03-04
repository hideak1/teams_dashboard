"""Pydantic models for team dashboard data structures."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    deleted = "deleted"


class AgentStatus(str, Enum):
    working = "working"
    idle = "idle"
    stopped = "stopped"
    lead = "lead"


# --- File system models (match ~/.claude/ JSON formats) ---


class TeamMember(BaseModel):
    agentId: str
    name: str
    agentType: str
    model: str = ""
    joinedAt: int = 0
    tmuxPaneId: str = ""
    cwd: str = ""
    subscriptions: list = Field(default_factory=list)
    prompt: str = ""
    color: str = ""
    planModeRequired: bool = False
    backendType: str = ""


class TeamConfig(BaseModel):
    name: str
    description: str = ""
    createdAt: int = 0
    leadAgentId: str = ""
    leadSessionId: str = ""
    members: list[TeamMember] = Field(default_factory=list)


class TaskFile(BaseModel):
    id: str
    subject: str = ""
    description: str = ""
    activeForm: str = ""
    owner: Optional[str] = None
    status: TaskStatus = TaskStatus.pending
    blocks: list[str] = Field(default_factory=list)
    blockedBy: list[str] = Field(default_factory=list)


class InboxMessage(BaseModel):
    from_: str = Field("", alias="from")
    text: str = ""
    summary: str = ""
    timestamp: str = ""
    read: bool = False

    model_config = {"populate_by_name": True}


# --- Hook event model ---


class HookEvent(BaseModel):
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""
    hook_event_name: str = ""
    tool_name: str = ""
    tool_input: dict | str = ""
    tool_result: dict | str = ""
    tool_use_id: str = ""
    # Stop event fields
    reason: str = ""
    last_assistant_message: str = ""
    # Custom metadata
    team_name: str = ""
    agent_name: str = ""


# --- API response models ---


class TeamOverview(BaseModel):
    name: str
    description: str = ""
    created_at: int = 0
    member_count: int = 0
    task_count: int = 0
    active: bool = True
    lead: str = ""


class AgentInfo(BaseModel):
    name: str
    agent_type: str = ""
    model: str = ""
    status: AgentStatus = AgentStatus.idle
    cwd: str = ""
    color: str = ""
    estimated_tokens: int = 0


class TaskInfo(BaseModel):
    id: str
    subject: str = ""
    active_form: str = ""
    owner: Optional[str] = None
    status: TaskStatus = TaskStatus.pending
    blocks: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)


class TeamDetail(BaseModel):
    name: str
    description: str = ""
    created_at: int = 0
    active: bool = True
    lead: str = ""
    agents: list[AgentInfo] = Field(default_factory=list)
    tasks: list[TaskInfo] = Field(default_factory=list)
    messages: list[InboxMessage] = Field(default_factory=list)


class TokenEstimate(BaseModel):
    agent_name: str
    estimated_tokens: int = 0
    label: str = "≈"


class GlobalStats(BaseModel):
    total_teams: int = 0
    active_teams: int = 0
    total_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    total_estimated_tokens: int = 0
    estimated_cost_sonnet: float = 0.0
    estimated_cost_opus: float = 0.0
