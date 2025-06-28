"""Zendesk API client."""

from typing import Any, Literal

from httpx import Client, Response

from .exceptions import TicketClosedError
from .models import Ticket, TicketComment


class ZendeskServices:
    """A class wrapping Zendesk interaction."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float,
    ) -> None:
        """Initialize the ZendeskServices class."""
        self.client = Client(
            base_url=base_url,
            auth=(username, password),
            timeout=timeout,
        )

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Response:
        """Make a request to Zendesk."""
        args: dict[str, str | dict[str, str]] = {
            "url": path,
            "method": method,
        }

        if params is not None:
            args["params"] = params

        if json is not None:
            args["json"] = json

        return self.client.request(**args)  # type: ignore[arg-type]

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

    def create_ticket(
        self,
        subject: str,
        body: str,
        group_id: int,
        priority: Literal["urgent", "high", "normal", "low"] = "normal",
    ) -> Ticket:
        """Find and load to base64."""
        response = self._make_request(
            method="POST",
            path="/api/v2/tickets",
            json={
                "ticket": {
                    "group_id": group_id,
                    "comment": {
                        "html_body": body,
                    },
                    "priority": priority,
                    "subject": subject,
                },
            },
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
