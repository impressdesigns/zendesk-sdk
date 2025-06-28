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
    tags: list[str]


class TicketComment(_BaseModel):
    """Ticket model."""

    id: int
    public: bool
    plain_body: str
    attachments: list[Attachment]
