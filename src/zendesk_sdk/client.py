"""Zendesk API client."""

from threading import Lock
from time import monotonic
from typing import Any, Literal

from httpx import BaseTransport, Client, HTTPError, Response
from pydantic import ValidationError

from .exceptions import TicketClosedError, ZendeskAuthenticationError, ZendeskConfigurationError
from .models import Ticket, TicketComment, _OAuthTokenResponse

_ACCESS_TOKEN_LIFETIME_SECONDS = 1800


class ZendeskServices:
    """A class wrapping Zendesk interaction."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
        timeout: float = 10.0,
        token_safety_skew: float = 30.0,
        transport: BaseTransport | None = None,
    ) -> None:
        """Initialize the ZendeskServices class."""
        required_settings = {
            "base_url": base_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        }
        for setting_name, setting_value in required_settings.items():
            if not setting_value.strip():
                message = f"{setting_name} must not be blank."
                raise ZendeskConfigurationError(message)
        if token_safety_skew < 0:
            message = "token_safety_skew must not be negative."
            raise ZendeskConfigurationError(message)

        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token_safety_skew = token_safety_skew
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._token_lock = Lock()
        self.client = Client(
            base_url=f"{base_url.rstrip('/')}/",
            timeout=timeout,
            transport=transport,
        )

    def _request_access_token(self) -> _OAuthTokenResponse:
        """Request and validate a client credentials access token."""
        try:
            response = self.client.post(
                "/oauth/tokens",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "expires_in": _ACCESS_TOKEN_LIFETIME_SECONDS,
                    "scope": self._scope,
                },
            )
        except HTTPError:
            message = "Zendesk OAuth token request could not be completed."
            raise ZendeskAuthenticationError(message) from None

        if response.is_error:
            message = f"Zendesk OAuth token request failed with HTTP {response.status_code}."
            raise ZendeskAuthenticationError(message)

        try:
            return _OAuthTokenResponse.model_validate(response.json())
        except (ValueError, ValidationError):
            message = "Zendesk OAuth token endpoint returned an invalid response."
            raise ZendeskAuthenticationError(message) from None

    def _get_access_token(self, *, stale_token: str | None = None) -> str:
        """Return a cached token, refreshing it when stale or near expiry."""
        with self._token_lock:
            if stale_token is not None and self._access_token == stale_token:
                self._access_token = None
                self._access_token_expires_at = 0.0

            if self._access_token is not None and monotonic() < self._access_token_expires_at - self._token_safety_skew:
                return self._access_token

            token = self._request_access_token()
            self._access_token = token.access_token
            self._access_token_expires_at = monotonic() + token.expires_in
            return token.access_token

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Make a request to Zendesk."""
        access_token = self._get_access_token()

        def send(token: str) -> Response:
            request_headers = dict(headers or {})
            request_headers["Authorization"] = f"Bearer {token}"
            return self.client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                headers=request_headers,
            )

        response = send(access_token)
        if response.status_code != 401:  # noqa: PLR2004
            return response

        refreshed_token = self._get_access_token(stale_token=access_token)
        return send(refreshed_token)

    def search(
        self,
        type_: Literal["ticket", "user", "organization"] = "ticket",
        statuses: list[Literal["new", "open", "pending", "hold", "solved", "closed"]] | None = None,
        tags: list[str] | None = None,
    ) -> list[Ticket]:
        """Search."""
        query = f"type:{type_}"
        if tags is not None:
            query += " " + " ".join(f'tags:"{tag}"' for tag in tags)
        if statuses is not None:
            query += " " + " ".join(f'status:"{status}"' for status in statuses)
        response = self._make_request(
            method="GET",
            path="/api/v2/search",
            params={"query": query},
        )
        response.raise_for_status()
        return [Ticket.model_validate(ticket) for ticket in response.json()["results"]]

    def get_ticket(self, ticket_id: int) -> Ticket:
        """Find and load to base64."""
        response = self._make_request(
            method="GET",
            path=f"/api/v2/tickets/{ticket_id}.json",
        )
        response.raise_for_status()
        return Ticket.model_validate(response.json()["ticket"])

    def create_ticket(  # noqa: PLR0913
        self,
        subject: str,
        body: str,
        *,
        requester_email: str,
        requester_name: str | None = None,
        tags: list[str] | None = None,
        group_id: int | None = None,
        priority: Literal["urgent", "high", "normal", "low"] = "normal",
        external_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ticket:
        """Create a ticket on behalf of a requester."""
        if not requester_email.strip():
            message = "requester_email must not be blank."
            raise ValueError(message)
        if requester_name is not None and not requester_name.strip():
            message = "requester_name must not be blank when provided."
            raise ValueError(message)
        if idempotency_key is not None and not idempotency_key.strip():
            message = "idempotency_key must not be blank when provided."
            raise ValueError(message)

        requester = {"email": requester_email}
        if requester_name is not None:
            requester["name"] = requester_name

        ticket: dict[str, Any] = {
            "comment": {
                "body": body,
            },
            "priority": priority,
            "requester": requester,
            "subject": subject,
        }
        if tags is not None:
            ticket["tags"] = tags
        if group_id is not None:
            ticket["group_id"] = group_id
        if external_id is not None:
            ticket["external_id"] = external_id

        headers = {"Idempotency-Key": idempotency_key} if idempotency_key is not None else None
        response = self._make_request(
            method="POST",
            path="/api/v2/tickets",
            json={"ticket": ticket},
            headers=headers,
        )
        response.raise_for_status()
        return Ticket.model_validate(response.json()["ticket"])

    def update_ticket(
        self,
        ticket_id: int,
        status: Literal["new", "open", "pending", "hold", "solved", "closed"] | None = None,
        comment: str | None = None,
        comment_is_public: bool = True,  # noqa: FBT001,FBT002
    ) -> Ticket:
        """Update a ticket."""
        args = {}
        if status is not None:
            args["status"] = status
        if comment is not None:
            args["comment"] = {  # type: ignore[assignment] # false positive
                "body": comment,
                "public": comment_is_public,
            }
        response = self._make_request(
            method="PUT",
            path=f"/api/v2/tickets/{ticket_id}",
            json={"ticket": args},
        )
        response.raise_for_status()
        return Ticket.model_validate(response.json()["ticket"])

    def add_tags_to_ticket(self, ticket_id: int, tags: list[str]) -> list[str]:
        """Add tags to a ticket."""
        ticket = self.get_ticket(ticket_id)
        if ticket.status == "closed":
            msg = f"Cannot add tags to a closed ticket (#{ticket_id})."
            raise TicketClosedError(msg)
        response = self._make_request(method="PUT", path=f"/api/v2/tickets/{ticket_id}/tags", json={"tags": tags})
        response.raise_for_status()
        return response.json()["tags"]  # type: ignore[no-any-return]

    def get_ticket_comments(self, ticket_id: int) -> list[TicketComment]:
        """Find and load to base64."""
        response = self._make_request(
            method="GET",
            path=f"/api/v2/tickets/{ticket_id}/comments",
        )
        response.raise_for_status()
        return [TicketComment.model_validate(comment) for comment in response.json()["comments"]]
