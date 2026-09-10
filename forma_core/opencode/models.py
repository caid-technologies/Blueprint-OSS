"""Explicit protocol models for the hosted OpenCode project agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from forma_core.workspaces.projects.models import HardwareIR, ValidationIssue


class OpenCodeSessionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class OpenCodeCommandStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OpenCodeOperation(str, Enum):
    PROJECT_MESSAGE = "project_message"
    COMPILE_PROJECT = "compile_project"
    VALIDATE_PROJECT = "validate_project"


class OpenCodeEventKind(str, Enum):
    ASSISTANT_MESSAGE = "assistant_message"
    QUEUED = "queued"
    WORKING = "working"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONNECTOR_UNAVAILABLE = "connector_unavailable"
    PROGRESS = "progress"


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    critical_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


class ProjectValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: tuple[ValidationIssue, ...] = ()


class PublicError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=300)
    correlation_id: str = Field(min_length=1, max_length=100)


class PublicEvent(BaseModel):
    """The only event shape that may cross the browser gateway."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1)
    session_id: str
    project_id: UUID
    kind: OpenCodeEventKind
    status: OpenCodeCommandStatus | None = None
    message: str | None = Field(default=None, max_length=2000)
    revision_id: str | None = None
    validation: ValidationSummary | None = None
    artifact_ids: tuple[str, ...] = ()
    error: PublicError | None = None
    created_at: datetime


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str = Field(min_length=1, max_length=120)
    project_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class SubmitCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=12_000)
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    connector_id: str
    project_id: UUID
    owner_user_id: str
    status: OpenCodeSessionStatus
    created_at: datetime
    updated_at: datetime


class CommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str
    session_id: str
    project_id: UUID
    operation: OpenCodeOperation
    status: OpenCodeCommandStatus
    attempt_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ConnectorCommand(BaseModel):
    """A leased command returned to the trusted mini-PC connector."""

    model_config = ConfigDict(extra="forbid")

    command_id: str
    session_id: str
    connector_id: str
    owner_user_id: str
    project_id: UUID
    operation: OpenCodeOperation
    message: str | None = None
    attempt_count: int = Field(ge=1)
    lease_expires_at: datetime
    lease_token: str = Field(min_length=1)


class ConnectorSession(BaseModel):
    """A session the authenticated connector is allowed to poll."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    connector_id: str
    project_id: UUID


class ConnectorSessionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: tuple[ConnectorSession, ...]


class ConnectorCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(min_length=1)


class ConnectorEventInput(BaseModel):
    """Allowlisted connector fields; all internal OpenCode fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=80)
    message: str | None = Field(default=None, max_length=10_000)
    status: OpenCodeCommandStatus | None = None
    project_id: UUID | None = None
    revision_id: str | None = Field(default=None, max_length=200)
    validation: ValidationSummary | None = None
    artifact_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=300)
    correlation_id: str | None = Field(default=None, max_length=100)


class ConnectorHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=1)


class ConnectorLeaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str
    status: OpenCodeCommandStatus
    lease_expires_at: datetime


class ConnectorCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=1)
    status: Literal[OpenCodeCommandStatus.SUCCEEDED, OpenCodeCommandStatus.FAILED, OpenCodeCommandStatus.CANCELLED]
    error_code: str | None = Field(default=None, max_length=80)


class McpToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_ir: HardwareIR | None = None


class McpRequestParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    arguments: McpToolArguments = Field(default_factory=McpToolArguments)


class McpJsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: str | int | None = None
    method: str
    params: McpRequestParams = Field(default_factory=McpRequestParams)


class ProjectToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    revision_id: str | None = None
    project_ir: HardwareIR
    validation: ProjectValidation
    mermaid_code: str
    svg_schematic: str


class ProjectScopeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    owner_user_id: str
    created: bool


class EventPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: tuple[PublicEvent, ...]
    next_cursor: int


class ConnectorCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
