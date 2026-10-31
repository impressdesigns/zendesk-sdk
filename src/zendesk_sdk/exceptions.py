"""Custom exceptions for the Zendesk API."""


class TicketClosedError(Exception):
    """Raised when a ticket is closed."""


class TicketUpdateConflictError(Exception):
    """Raised when a safe update finds the ticket changed after ``updated_stamp``."""
