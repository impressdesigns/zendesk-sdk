"""HTTP-level tests for the Zendesk client."""

import json
from collections.abc import Callable

import httpx
import pytest

import zendesk_sdk.client as client_module
from zendesk_sdk import ZendeskAuthenticationError, ZendeskConfigurationError, ZendeskServices


def _build_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    token_safety_skew: float = 30.0,
) -> ZendeskServices:
    """Build a client backed by an in-memory HTTP transport."""
    return ZendeskServices(
        base_url="https://example.zendesk.com",
        client_id="idi_core_zendesk",
        client_secret="oauth-secret",
        scope="tickets:write",
        token_safety_skew=token_safety_skew,
        transport=httpx.MockTransport(handler),
    )


def _ticket_response(request: httpx.Request, ticket_id: int = 123) -> httpx.Response:
    """Return a valid Zendesk ticket response."""
    return httpx.Response(
        200,
        json={
            "ticket": {
                "id": ticket_id,
                "status": "new",
                "url": f"https://example.zendesk.com/api/v2/tickets/{ticket_id}.json",
                "created_at": "2026-08-27T12:00:00Z",
                "tags": ["iditoolscarrierreturn"],
            },
        },
        request=request,
    )


def _token_response(request: httpx.Request, access_token: str, expires_in: int = 1800) -> httpx.Response:
    """Return a valid Zendesk OAuth token response."""
    return httpx.Response(
        200,
        json={
            "access_token": access_token,
            "token_type": "bearer",
            "scope": "tickets:write",
            "expires_in": expires_in,
        },
        request=request,
    )


@pytest.mark.parametrize(
    ("base_url", "client_id", "client_secret", "scope", "setting_name"),
    [
        (" ", "idi_core_zendesk", "oauth-secret", "tickets:write", "base_url"),
        ("https://example.zendesk.com", " ", "oauth-secret", "tickets:write", "client_id"),
        ("https://example.zendesk.com", "idi_core_zendesk", " ", "tickets:write", "client_secret"),
        ("https://example.zendesk.com", "idi_core_zendesk", "oauth-secret", " ", "scope"),
    ],
)
def test_blank_oauth_configuration_is_rejected(
    base_url: str,
    client_id: str,
    client_secret: str,
    scope: str,
    setting_name: str,
) -> None:
    """Required OAuth settings fail closed before any HTTP request."""
    with pytest.raises(ZendeskConfigurationError, match=rf"^{setting_name} must not be blank\.$"):
        ZendeskServices(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )


def test_negative_token_safety_skew_is_rejected() -> None:
    """A negative expiry safety window is invalid configuration."""
    with pytest.raises(ZendeskConfigurationError, match="token_safety_skew"):
        ZendeskServices(
            base_url="https://example.zendesk.com",
            client_id="idi_core_zendesk",
            client_secret="oauth-secret",
            scope="tickets:write",
            token_safety_skew=-1,
        )


def test_client_credentials_token_is_json_encoded_and_cached() -> None:
    """The first API call gets a JSON-requested token and later calls reuse it."""
    token_requests = 0
    api_authorizations: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/oauth/tokens":
            token_requests += 1
            assert request.method == "POST"
            assert request.headers["Content-Type"] == "application/json"
            assert json.loads(request.content) == {
                "grant_type": "client_credentials",
                "client_id": "idi_core_zendesk",
                "client_secret": "oauth-secret",
                "expires_in": 1800,
                "scope": "tickets:write",
            }
            assert "Authorization" not in request.headers
            return _token_response(request, "cached-token")
        if request.url.path == "/api/v2/tickets/123.json":
            api_authorizations.append(request.headers["Authorization"])
            return _ticket_response(request)
        message = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(message)

    client = _build_client(handler)

    assert client.get_ticket(123).id == 123
    assert client.get_ticket(123).id == 123
    assert token_requests == 1
    assert api_authorizations == ["Bearer cached-token", "Bearer cached-token"]


def test_cached_token_refreshes_at_expiry_safety_skew(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token is refreshed when it reaches its safety-adjusted expiry."""
    now = [100.0]
    token_requests = 0
    api_authorizations: list[str] = []
    monkeypatch.setattr(client_module, "monotonic", lambda: now[0])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/oauth/tokens":
            token_requests += 1
            return _token_response(request, f"token-{token_requests}", expires_in=100)
        api_authorizations.append(request.headers["Authorization"])
        return _ticket_response(request)

    client = _build_client(handler, token_safety_skew=10)

    client.get_ticket(123)
    now[0] = 189.0
    client.get_ticket(123)
    now[0] = 190.0
    client.get_ticket(123)

    assert token_requests == 2
    assert api_authorizations == ["Bearer token-1", "Bearer token-1", "Bearer token-2"]


def test_unauthorized_api_request_forces_one_refresh_and_retry() -> None:
    """A 401 invalidates the cached token and retries with a new token."""
    token_requests = 0
    api_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/oauth/tokens":
            token_requests += 1
            return _token_response(request, f"token-{token_requests}")
        api_requests.append(request)
        if len(api_requests) == 1:
            return httpx.Response(401, request=request)
        return _ticket_response(request)

    client = _build_client(handler)
    ticket = client.get_ticket(123)

    assert ticket.id == 123
    assert token_requests == 2
    assert [request.headers["Authorization"] for request in api_requests] == ["Bearer token-1", "Bearer token-2"]


def test_second_unauthorized_response_is_not_retried() -> None:
    """A persistent 401 is returned after exactly one refresh attempt."""
    token_requests = 0
    api_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal api_requests, token_requests
        if request.url.path == "/oauth/tokens":
            token_requests += 1
            return _token_response(request, f"token-{token_requests}")
        api_requests += 1
        return httpx.Response(401, request=request)

    client = _build_client(handler)

    with pytest.raises(httpx.HTTPStatusError, match="401 Unauthorized"):
        client.get_ticket(123)

    assert token_requests == 2
    assert api_requests == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": "invalid_client"}),
        httpx.Response(200, json={"access_token": "", "expires_in": 1800}),
        httpx.Response(200, json={"access_token": "token-without-expiry"}),
        httpx.Response(200, text="not-json"),
    ],
)
def test_oauth_failures_raise_sanitized_authentication_error(response: httpx.Response) -> None:
    """OAuth failures do not expose the configured client secret."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=response.headers,
            request=request,
        )

    client = _build_client(handler)

    with pytest.raises(ZendeskAuthenticationError) as error:
        client.get_ticket(123)

    assert "oauth-secret" not in str(error.value)


def test_oauth_transport_error_raises_sanitized_authentication_error() -> None:
    """A token transport failure is wrapped without exposing sensitive details."""

    def handler(request: httpx.Request) -> httpx.Response:
        message = "Network failure involving oauth-secret"
        raise httpx.ConnectError(message, request=request)

    client = _build_client(handler)

    with pytest.raises(ZendeskAuthenticationError) as error:
        client.get_ticket(123)

    assert str(error.value) == "Zendesk OAuth token request could not be completed."
    assert "oauth-secret" not in str(error.value)
    assert error.value.__cause__ is None
