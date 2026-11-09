"""Zendesk API models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


class _BaseModel(PydanticBaseModel, strict=True):
    """Base model for all Zendesk models."""


class Attachment(_BaseModel):
    """Attachment model."""

    id: int
    url: str
    file_name: str
    content_url: str


class Ticket(_BaseModel):
    """Ticket model."""

    id: int
    status: Literal["new", "open", "pending", "hold", "solved", "closed"]
    url: str
    created_at: datetime = Field(strict=False)
    updated_at: datetime = Field(strict=False)
    tags: list[str]
    subject: str | None = None
    description: str | None = None
    priority: Literal["urgent", "high", "normal", "low"] | None = None
    requester_id: int | None = None
    submitter_id: int | None = None
    assignee_id: int | None = None
    group_id: int | None = None
    collaborator_ids: list[int] = Field(default_factory=list)


class TicketComment(_BaseModel):
    """One comment on a ticket, public or internal."""

    id: int
    public: bool
    plain_body: str
    attachments: list[Attachment]
    author_id: int | None = None
    created_at: datetime | None = Field(default=None, strict=False)


class TicketCommentPage(_BaseModel):
    """One cursor page of ticket comments for the caller to traverse."""

    comments: list[TicketComment]
    has_more: bool
    after_cursor: str | None


class User(_BaseModel):
    """A Zendesk user: an end user (requester) or a staff member."""

    id: int
    name: str
    email: str | None
    role: Literal["end-user", "agent", "admin"]


class IncrementalTicketPage(_BaseModel):
    """One page of the incremental ticket export for the caller to traverse."""

    tickets: list[Ticket]
    after_cursor: str | None
    end_of_stream: bool
