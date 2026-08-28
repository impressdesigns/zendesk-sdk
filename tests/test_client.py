"""Testing the client."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from zendesk_sdk import ZendeskServices

CREATED_TICKET_ID = 987654321
TICKET = {
    "id": 1,
    "status": "open",
    "url": "https://example.zendesk.com/api/v2/tickets/1.json",
    "created_at": "2026-08-28T12:00:00Z",
    "tags": [],
}


def _build_client() -> ZendeskServices:
    """Build a client with placeholder OAuth credentials."""
    return ZendeskServices(
        base_url="https://example.zendesk.com",
        client_id="example-client-id",
        client_secret="example-client-secret",  # noqa: S106
        scope="tickets:read tickets:write",
        timeout=10.0,
    )


def _response(payload: dict[str, object]) -> MagicMock:
    """Stand in for a successful response."""
    response = MagicMock()
    response.json.return_value = payload
    return response


def _stub_session(
    client: ZendeskServices,
    monkeypatch: pytest.MonkeyPatch,
    expires_in: int,
) -> tuple[list[tuple[str, dict[str, object]]], list[object]]:
    """Answer token and API calls in memory, recording both sides of the exchange.

    Each token request is answered with a distinct token, so a refresh is visible in the
    credentials the API requests were sent with.
    """
    token_requests: list[tuple[str, dict[str, object]]] = []
    sent_credentials: list[object] = []

    def post(url: str, json: dict[str, object]) -> MagicMock:
        token_requests.append((url, json))
        return _response({"access_token": f"access-token-{len(token_requests)}", "expires_in": expires_in})

    def request(**kwargs: object) -> MagicMock:
        sent_credentials.append(kwargs["auth"])
        return _response({"ticket": TICKET})

    monkeypatch.setattr(client.client, "post", post)
    monkeypatch.setattr(client.client, "request", request)
    return token_requests, sent_credentials


def test_access_token_is_reused_until_it_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """A client credentials token is requested once and sent as a bearer token."""
    client = _build_client()
    token_requests, sent_credentials = _stub_session(client, monkeypatch, expires_in=1800)

    client.get_ticket(1)
    client.get_ticket(1)

    expected_token_request: tuple[str, dict[str, object]] = (
        "/oauth/tokens",
        {
            "grant_type": "client_credentials",
            "client_id": "example-client-id",
            "client_secret": "example-client-secret",
            "scope": "tickets:read tickets:write",
        },
    )
    assert token_requests == [expected_token_request]
    assert sent_credentials == ["access-token-1", "access-token-1"]


def test_expired_access_token_is_requested_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired token is replaced before the next request goes out."""
    client = _build_client()
    _, sent_credentials = _stub_session(client, monkeypatch, expires_in=0)

    client.get_ticket(1)
    client.get_ticket(1)

    assert sent_credentials == ["access-token-1", "access-token-2"]


def test_create_ticket_sends_all_supported_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ticket creation sends requester, tags, routing, identity, and idempotency."""
    client = _build_client()
    ticket_requests: list[dict[str, object]] = []

    def post(url: str, json: dict[str, object]) -> MagicMock:
        assert url == "/oauth/tokens"
        assert json["grant_type"] == "client_credentials"
        return _response({"access_token": "access-token", "expires_in": 1800})

    def request(**kwargs: object) -> MagicMock:
        ticket_requests.append(kwargs)
        ticket = dict(TICKET)
        ticket["id"] = CREATED_TICKET_ID
        return _response({"ticket": ticket})

    monkeypatch.setattr(client.client, "post", post)
    monkeypatch.setattr(client.client, "request", request)

    ticket = client.create_ticket(
        "Returned order 1001",
        "Return details\n \nPlease advise.",
        requester_email="customer@example.com",
        requester_name="Customer Name",
        tags=["iditoolscarrierreturn", "rts-52"],
        group_id=42,
        priority="high",
        external_id="carrier-return:52",
        idempotency_key="carrier-return:52",
    )

    assert ticket.id == CREATED_TICKET_ID
    assert ticket_requests == [
        {
            "url": "/api/v2/tickets",
            "method": "POST",
            "auth": "access-token",
            "json": {
                "ticket": {
                    "comment": {"body": "Return details\n \nPlease advise.", "public": True},
                    "external_id": "carrier-return:52",
                    "group_id": 42,
                    "priority": "high",
                    "requester": {"email": "customer@example.com", "name": "Customer Name"},
                    "subject": "Returned order 1001",
                    "tags": ["iditoolscarrierreturn", "rts-52"],
                },
            },
            "headers": {"Idempotency-Key": "carrier-return:52"},
        },
    ]


def test_create_ticket_omits_optional_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional ticket fields and the idempotency header are omitted when unset."""
    client = _build_client()
    ticket_requests: list[dict[str, object]] = []

    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )

    def request(**kwargs: object) -> MagicMock:
        ticket_requests.append(kwargs)
        return _response({"ticket": TICKET})

    monkeypatch.setattr(client.client, "request", request)

    client.create_ticket(
        "Subject",
        "Body",
        requester_email="existing@example.com",
        requester_name="Existing Customer",
    )

    assert ticket_requests == [
        {
            "url": "/api/v2/tickets",
            "method": "POST",
            "auth": "access-token",
            "json": {
                "ticket": {
                    "comment": {"body": "Body", "public": True},
                    "priority": "normal",
                    "requester": {"email": "existing@example.com", "name": "Existing Customer"},
                    "subject": "Subject",
                },
            },
        },
    ]


@pytest.mark.parametrize(
    ("keyword_arguments", "expected_message"),
    [
        ({"requester_email": " ", "requester_name": "Customer Name"}, "requester_email"),
        ({"requester_email": "customer@example.com", "requester_name": " "}, "requester_name"),
        (
            {
                "requester_email": "customer@example.com",
                "requester_name": "Customer Name",
                "idempotency_key": " ",
            },
            "idempotency_key",
        ),
    ],
)
def test_create_ticket_rejects_blank_values(
    monkeypatch: pytest.MonkeyPatch,
    keyword_arguments: dict[str, Any],
    expected_message: str,
) -> None:
    """Invalid ticket inputs fail before an HTTP request is sent."""
    client = _build_client()
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: pytest.fail("Invalid input must not request an access token."),
    )

    with pytest.raises(ValueError, match=expected_message):
        client.create_ticket("Subject", "Body", **keyword_arguments)
