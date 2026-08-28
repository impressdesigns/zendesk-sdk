"""Zendesk API client."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from niquests import Response, Session

from .exceptions import TicketClosedError
from .models import Ticket, TicketComment

# Refresh a little early so a request issued at the boundary does not race the expiry.
TOKEN_EXPIRY_MARGIN = timedelta(seconds=30)


class ZendeskServices:
    """A class wrapping Zendesk interaction."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
        timeout: float,
    ) -> None:
        """Initialize the ZendeskServices class."""
        self.client = Session(
            base_url=base_url,
            timeout=timeout,
        )
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._access_token: str | None = None
        self._access_token_expires_at = datetime.min.replace(tzinfo=UTC)

    def _get_access_token(self) -> str:
        """Return an access token, requesting a new one when the cached one has expired."""
        if self._access_token is not None and datetime.now(UTC) < self._access_token_expires_at:
            return self._access_token

        response = self.client.post(
            "/oauth/tokens",
            json={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
        )
        response.raise_for_status()
        token = response.json()

        access_token: str = token["access_token"]
        self._access_token = access_token
        self._access_token_expires_at = datetime.now(UTC) + timedelta(seconds=token["expires_in"]) - TOKEN_EXPIRY_MARGIN
        return access_token

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Make a request to Zendesk."""
        args: dict[str, str | dict[str, str]] = {
            "url": path,
            "method": method,
            "auth": self._get_access_token(),
        }

        if params is not None:
            args["params"] = params

        if json is not None:
            args["json"] = json

        if headers is not None:
            args["headers"] = headers

        return self.client.request(**args)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

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
        requester_name: str,
        tags: list[str] | None = None,
        group_id: int | None = None,
        priority: Literal["urgent", "high", "normal", "low"] = "normal",
        external_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ticket:
        """Create a public ticket on behalf of a requester."""
        if not requester_email.strip():
            message = "requester_email must not be blank."
            raise ValueError(message)
        if not requester_name.strip():
            message = "requester_name must not be blank."
            raise ValueError(message)
        if idempotency_key is not None and not idempotency_key.strip():
            message = "idempotency_key must not be blank when provided."
            raise ValueError(message)

        requester = {"email": requester_email, "name": requester_name}

        ticket: dict[str, Any] = {
            "comment": {
                "body": body,
                "public": True,
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
