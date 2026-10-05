"""Interface to Zendesk API."""

from .client import ZendeskServices
from .exceptions import TicketClosedError
from .models import Attachment, Ticket, TicketComment, TicketCommentPage

__all__ = ["Attachment", "Ticket", "TicketClosedError", "TicketComment", "TicketCommentPage", "ZendeskServices"]
