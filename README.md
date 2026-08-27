# Zendesk SDK

A synchronous Python client for the Zendesk Ticketing API.

## Authentication

The SDK uses Zendesk's confidential OAuth client credentials flow. Create a
confidential OAuth client in Zendesk, keep its secret on the server, and grant
only the scopes the integration needs. API-token and password-based Basic
authentication are not supported.

```python
import os

from zendesk_sdk import ZendeskServices

zendesk = ZendeskServices(
    base_url="https://example.zendesk.com",
    client_id=os.environ["ZENDESK_CLIENT_ID"],
    client_secret=os.environ["ZENDESK_CLIENT_SECRET"],
    scope="tickets:write",
)
```

The SDK requests 30-minute access tokens and caches them in memory until shortly
before expiry. An API request that receives a `401 Unauthorized` response
refreshes the token and is retried once.
