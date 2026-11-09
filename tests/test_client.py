"""Testing the client."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

import pytest

from zendesk_sdk import Attachment, TicketUpdateConflictError, ZendeskServices

CREATED_TICKET_ID = 987654321
TICKET = {
    "id": 1,
    "status": "open",
    "url": "https://example.zendesk.com/api/v2/tickets/1.json",
    "created_at": "2026-08-28T12:00:00Z",
    "updated_at": "2026-08-28T12:30:00Z",
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


def test_create_ticket_can_open_with_an_internal_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller that asks for a private first comment gets one."""
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
        requester_email="customer@example.com",
        requester_name="Customer Name",
        comment_is_public=False,
    )

    assert ticket_requests == [
        {
            "url": "/api/v2/tickets",
            "method": "POST",
            "auth": "access-token",
            "json": {
                "ticket": {
                    "comment": {"body": "Body", "public": False},
                    "priority": "normal",
                    "requester": {"email": "customer@example.com", "name": "Customer Name"},
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


def test_update_ticket_sends_private_note_with_safe_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """A private note uses the ticket's last update timestamp to detect collisions."""
    client = _build_client()
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )

    def request(**kwargs: object) -> MagicMock:
        requests.append(kwargs)
        return _response({"ticket": TICKET})

    monkeypatch.setattr(client.client, "request", request)
    ticket = client.update_ticket(
        1,
        comment="RTS 52: cartons received",
        comment_is_public=False,
        updated_stamp=datetime(2026, 8, 28, 12, 30, tzinfo=UTC),
    )

    assert ticket.updated_at == datetime(2026, 8, 28, 12, 30, tzinfo=UTC)
    assert requests == [
        {
            "url": "/api/v2/tickets/1",
            "method": "PUT",
            "auth": "access-token",
            "json": {
                "ticket": {
                    "comment": {"body": "RTS 52: cartons received", "public": False},
                    "safe_update": True,
                    "updated_stamp": "2026-08-28T12:30:00Z",
                },
            },
        },
    ]


def test_update_ticket_raises_conflict_when_stamp_is_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """A safe update rejected by Zendesk surfaces as a conflict the caller can catch."""
    client = _build_client()
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )
    conflict = _response({"error": "UpdateConflict"})
    conflict.status_code = HTTPStatus.CONFLICT
    monkeypatch.setattr(client.client, "request", lambda **_kwargs: conflict)

    with pytest.raises(TicketUpdateConflictError):
        client.update_ticket(1, comment="note", updated_stamp=datetime(2026, 8, 28, 12, 30, tzinfo=UTC))


def test_update_ticket_rejects_naive_stamp_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ambiguous local timestamp must never become a conditional update."""
    client = _build_client()
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: pytest.fail("Invalid input must not request an access token."),
    )

    with pytest.raises(ValueError, match="timezone"):
        client.update_ticket(
            1, comment="note", updated_stamp=datetime(2026, 8, 28, 12, 30, tzinfo=UTC).replace(tzinfo=None)
        )


def test_get_ticket_comments_page_exposes_cursor_for_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """The caller chooses when to request each comment page."""
    client = _build_client()
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )
    pages: list[dict[str, object]] = [
        {
            "comments": [{"id": 1, "public": False, "plain_body": "first", "attachments": []}],
            "meta": {"has_more": True, "after_cursor": "next-cursor"},
        },
        {
            "comments": [{"id": 2, "public": False, "plain_body": "second", "attachments": []}],
            "meta": {"has_more": False, "after_cursor": None},
        },
    ]

    def request(**kwargs: object) -> MagicMock:
        requests.append(kwargs)
        return _response(pages[len(requests) - 1])

    monkeypatch.setattr(client.client, "request", request)
    first = client.get_ticket_comments_page(1)
    second = client.get_ticket_comments_page(1, after_cursor=first.after_cursor)

    assert [comment.id for comment in first.comments] == [1]
    assert first.has_more is True
    assert first.after_cursor == "next-cursor"
    assert [comment.id for comment in second.comments] == [2]
    assert second.has_more is False
    assert [request["params"] for request in requests] == [
        {"page[size]": 100},
        {"page[size]": 100, "page[after]": "next-cursor"},
    ]


def test_get_ticket_comments_page_rejects_incomplete_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing cursor must not make a page look complete."""
    client = _build_client()
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )
    monkeypatch.setattr(
        client.client,
        "request",
        lambda **_kwargs: _response({"comments": [], "meta": {"has_more": True, "after_cursor": None}}),
    )

    with pytest.raises(ValueError, match="cursor"):
        client.get_ticket_comments_page(1)


def test_get_ticket_comments_fetches_pages_on_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each page is requested only when the caller iterates past the previous one."""
    client = _build_client()
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )
    pages: list[dict[str, object]] = [
        {
            "comments": [{"id": 1, "public": True, "plain_body": "first", "attachments": []}],
            "meta": {"has_more": True, "after_cursor": "next-cursor"},
        },
        {
            "comments": [{"id": 2, "public": False, "plain_body": "second", "attachments": []}],
            "meta": {"has_more": False, "after_cursor": None},
        },
    ]
    requests: list[dict[str, object]] = []

    def request(**kwargs: object) -> MagicMock:
        requests.append(kwargs)
        return _response(pages[len(requests) - 1])

    monkeypatch.setattr(client.client, "request", request)
    comments = client.get_ticket_comments(1)

    assert requests == []
    assert next(comments).id == 1
    assert len(requests) == 1
    assert [comment.id for comment in comments] == [2]
    assert len(requests) == len(pages)


def _stub_api(
    client: ZendeskServices,
    monkeypatch: pytest.MonkeyPatch,
    payloads: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Answer token requests and replay API payloads in order, recording each API request."""
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(
        client.client,
        "post",
        lambda *_args, **_kwargs: _response({"access_token": "access-token", "expires_in": 1800}),
    )

    def request(**kwargs: object) -> MagicMock:
        requests.append(kwargs)
        return _response(payloads[len(requests) - 1])

    monkeypatch.setattr(client.client, "request", request)
    return requests


def test_ticket_carries_the_fields_a_mirror_needs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subject, description, people, group and priority come through when Zendesk sends them."""
    client = _build_client()
    ticket = TICKET | {
        "subject": "Printer jammed",
        "description": "Tray 2 again",
        "priority": "high",
        "requester_id": 11,
        "submitter_id": 11,
        "assignee_id": 22,
        "group_id": 33,
        "collaborator_ids": [44],
    }
    _stub_api(client, monkeypatch, [{"ticket": ticket}])

    loaded = client.get_ticket(1)

    assert (loaded.subject, loaded.description, loaded.priority) == ("Printer jammed", "Tray 2 again", "high")
    assert (loaded.requester_id, loaded.assignee_id, loaded.group_id) == (11, 22, 33)
    assert loaded.collaborator_ids == [44]


def test_comment_carries_its_author_and_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """A comment says who wrote it and when, so a copy can keep both."""
    client = _build_client()
    comment = {
        "id": 5,
        "public": True,
        "plain_body": "Thanks",
        "attachments": [],
        "author_id": 11,
        "created_at": "2026-11-09T08:00:00Z",
    }
    _stub_api(client, monkeypatch, [{"comments": [comment], "meta": {"has_more": False, "after_cursor": None}}])

    [loaded] = client.get_ticket_comments_page(1).comments

    assert (loaded.author_id, loaded.created_at) == (11, datetime(2026, 11, 9, 8, tzinfo=UTC))


def test_get_users_loads_many_in_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Users are fetched together by id."""
    client = _build_client()
    users = [
        {"id": 11, "name": "Requester", "email": "requester@example.com", "role": "end-user"},
        {"id": 22, "name": "Agent", "email": None, "role": "agent"},
    ]
    requests = _stub_api(client, monkeypatch, [{"users": users}])

    loaded = client.get_users([11, 22])

    assert [(user.id, user.email, user.role) for user in loaded] == [
        (11, "requester@example.com", "end-user"),
        (22, None, "agent"),
    ]
    assert [request["params"] for request in requests] == [{"ids": "11,22"}]


def test_get_users_refuses_more_than_zendesk_accepts() -> None:
    """Zendesk's show_many takes 100 ids; the caller splits larger lists."""
    with pytest.raises(ValueError, match="100"):
        _build_client().get_users(list(range(101)))


def test_get_users_with_no_ids_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty list needs no request."""
    client = _build_client()
    requests = _stub_api(client, monkeypatch, [])

    assert client.get_users([]) == []
    assert requests == []


def test_incremental_tickets_start_at_a_time_then_follow_the_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first page starts at a time; later pages follow the previous cursor until the stream ends."""
    client = _build_client()
    pages: list[dict[str, object]] = [
        {"tickets": [TICKET], "after_cursor": "next-cursor", "end_of_stream": False},
        {"tickets": [], "after_cursor": "caught-up", "end_of_stream": True},
    ]
    requests = _stub_api(client, monkeypatch, pages)

    first = client.get_incremental_tickets_page(start_time=datetime(2026, 11, 9, tzinfo=UTC))
    second = client.get_incremental_tickets_page(cursor=first.after_cursor)

    assert [ticket.id for ticket in first.tickets] == [1]
    assert (first.after_cursor, first.end_of_stream) == ("next-cursor", False)
    assert (second.after_cursor, second.end_of_stream) == ("caught-up", True)
    assert [request["params"] for request in requests] == [
        {"exclude_deleted": "true", "start_time": 1794182400},
        {"exclude_deleted": "true", "cursor": "next-cursor"},
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"start_time": datetime(2026, 11, 9, tzinfo=UTC), "cursor": "both"},
        {"cursor": " "},
        {"start_time": datetime(2026, 11, 9)},  # noqa: DTZ001 - the naive time is the point
    ],
)
def test_incremental_tickets_refuse_ambiguous_starts(kwargs: dict[str, Any]) -> None:
    """Exactly one of a timezone-aware start time or a non-blank cursor."""
    with pytest.raises(ValueError, match=r"start_time|cursor|timezone"):
        _build_client().get_incremental_tickets_page(**kwargs)


def test_download_attachment_reads_its_content_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """An attachment downloads from its own content URL with the client's token."""
    client = _build_client()
    requests = _stub_api(client, monkeypatch, [])
    attachment = Attachment.model_validate(
        {
            "id": 5,
            "url": "https://example.zendesk.com/api/v2/attachments/5.json",
            "file_name": "label.pdf",
            "content_url": "https://example.zendesk.com/attachments/token/abc/?name=label.pdf",
            "content_type": "application/pdf",
            "size": 3,
        }
    )

    def request(**kwargs: object) -> MagicMock:
        requests.append(kwargs)
        response = _response({})
        response.content = b"pdf"
        return response

    monkeypatch.setattr(client.client, "request", request)

    assert client.download_attachment(attachment) == b"pdf"
    assert [(request["method"], request["url"], request["auth"]) for request in requests] == [
        ("GET", attachment.content_url, "access-token"),
    ]
    assert (attachment.content_type, attachment.size) == ("application/pdf", 3)
