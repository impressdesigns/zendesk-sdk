"""Custom exceptions for the Zendesk API."""


class ZendeskAuthenticationError(RuntimeError):
    """Raised when Zendesk OAuth authentication cannot be completed."""


class ZendeskConfigurationError(ValueError):
    """Raised when required Zendesk client configuration is invalid."""


class TicketClosedError(Exception):
    """Raised when a ticket is closed."""
