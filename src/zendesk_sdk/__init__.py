"""Interface to Zendesk API."""

from .client import ZendeskServices
from .exceptions import TicketClosedError, TicketUpdateConflictError
from .models import (
    Attachment,
    IncrementalTicketPage,
    Ticket,
    TicketAudit,
    TicketAuditEvent,
    TicketAuditPage,
    TicketComment,
    TicketCommentPage,
    User,
)

__all__ = [
    "Attachment",
    "IncrementalTicketPage",
    "Ticket",
    "TicketAudit",
    "TicketAuditEvent",
    "TicketAuditPage",
    "TicketClosedError",
    "TicketComment",
    "TicketCommentPage",
    "TicketUpdateConflictError",
    "User",
    "ZendeskServices",
]
