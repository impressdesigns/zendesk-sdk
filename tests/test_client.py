"""Testing the client."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from zendesk_sdk import ZendeskServices

if TYPE_CHECKING:
    import pytest

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
