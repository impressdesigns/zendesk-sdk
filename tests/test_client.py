"""Testing the client."""

from zendesk_sdk import ZendeskServices


def test_smoke() -> None:
    """Temporary test to check if the tests are running."""
    client = ZendeskServices(
        base_url="https://example.zendesk.com/api/v2",
        username="",
        password="",
        timeout=10.0,
    )
    assert client is not None
