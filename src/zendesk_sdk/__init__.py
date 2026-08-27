"""Interface to Zendesk API."""

from .client import ZendeskServices
from .exceptions import TicketClosedError, ZendeskAuthenticationError, ZendeskConfigurationError
from .models import Attachment, Ticket, TicketComment

__all__ = [
    "Attachment",
    "Ticket",
    "TicketClosedError",
    "TicketComment",
    "ZendeskAuthenticationError",
    "ZendeskConfigurationError",
    "ZendeskServices",
]
