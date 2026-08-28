Authentication
==============

The SDK authenticates with the OAuth 2.0 client credentials grant. Zendesk has
`removed API tokens <https://support.zendesk.com/hc/en-us/articles/10851263566234-Announcing-the-removal-of-API-tokens-as-an-authentication-method-for-API-requests>`_
as an authentication method, and only OAuth is supported here.

Create a confidential OAuth client in the Zendesk Admin Center, grant it only the scopes
the integration needs, and keep its secret out of source control. Pass the credentials to
:class:`~zendesk_sdk.client.ZendeskServices`:

.. code-block:: python

   from zendesk_sdk import ZendeskServices

   zendesk = ZendeskServices(
       base_url="https://your-subdomain.zendesk.com",
       client_id="your-oauth-client-id",
       client_secret="your-oauth-client-secret",
       scope="tickets:read tickets:write",
       timeout=10.0,
   )

The client requests an access token the first time it needs one, reuses it until it
expires, and requests a new one after that.
