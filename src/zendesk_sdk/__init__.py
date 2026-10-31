"""Interface to Zendesk API."""

from .client import ZendeskServices
from .exceptions import TicketClosedError, TicketUpdateConflictError
from .models import Attachment, Ticket, TicketComment, TicketCommentPage

__all__ = [
    "Attachment",
    "Ticket",
    "TicketClosedError",
    "TicketComment",
    "TicketCommentPage",
    "TicketUpdateConflictError",
    "ZendeskServices",
]
