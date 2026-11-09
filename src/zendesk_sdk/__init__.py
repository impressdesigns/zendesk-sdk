"""Interface to Zendesk API."""

from .client import ZendeskServices
from .exceptions import TicketClosedError, TicketUpdateConflictError
from .models import Attachment, IncrementalTicketPage, Ticket, TicketComment, TicketCommentPage, User

__all__ = [
    "Attachment",
    "IncrementalTicketPage",
    "Ticket",
    "TicketClosedError",
    "TicketComment",
    "TicketCommentPage",
    "TicketUpdateConflictError",
    "User",
    "ZendeskServices",
]
