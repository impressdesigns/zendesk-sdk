"""Zendesk API models."""

from datetime import datetime
from typing import Any, Literal

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
    content_type: str | None = None
    size: int | None = None


class Ticket(_BaseModel):
    """Ticket model."""

    id: int
    #: ``deleted`` only comes from the incremental export asked to include deleted tickets.
    status: Literal["new", "open", "pending", "hold", "solved", "closed", "deleted"]
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
    #: The comment as Zendesk formatted it, which is the body an emailed comment keeps its
    #: tables, links and images in.
    html_body: str | None = None
    attachments: list[Attachment]
    author_id: int | None = None
    created_at: datetime | None = Field(default=None, strict=False)


class TicketCommentPage(_BaseModel):
    """One cursor page of ticket comments for the caller to traverse."""

    comments: list[TicketComment]
    has_more: bool
    after_cursor: str | None


class TicketAuditEvent(_BaseModel):
    """One thing an audit did to its ticket.

    ``type`` says which: ``Create`` set a field as the ticket was opened, ``Change`` moved one,
    ``Comment`` added a comment, and Zendesk has many more. Only ``Create`` and ``Change`` carry
    ``field_name``, and only ``Change`` carries ``previous_value``. A value is normally a string,
    an id included (``"360004442691"``); tags are a list, and some fields are an object.
    """

    id: int
    type: str
    field_name: str | None = None
    value: str | int | bool | list[Any] | dict[str, Any] | None = None
    previous_value: str | int | bool | list[Any] | dict[str, Any] | None = None


class TicketAudit(_BaseModel):
    """One update to a ticket: who made it, when, and what it changed.

    ``author_id`` is whoever made the update. An update a trigger or an automation made names
    no user Zendesk can load, so look the id up before treating it as a person.

    ``metadata`` is Zendesk's own record of where the update came from, passed through as sent.
    Zendesk documents its ``system`` and ``custom`` objects and not their keys, so read a key
    as optional.
    """

    id: int
    ticket_id: int
    created_at: datetime = Field(strict=False)
    author_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    events: list[TicketAuditEvent]


class TicketAuditPage(_BaseModel):
    """One cursor page of a ticket's audits for the caller to traverse."""

    audits: list[TicketAudit]
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
