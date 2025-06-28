"""Custom exceptions for the Zendesk API."""


class TicketClosedError(Exception):
    """Raised when a ticket is closed."""
