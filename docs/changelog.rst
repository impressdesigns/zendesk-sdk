Changelog
=========

- :feature:`60` ``update_ticket`` takes an optional ``updated_stamp`` for Zendesk safe updates and raises ``TicketUpdateConflictError`` when the ticket changed in the meantime. ``Ticket`` now has ``updated_at``.
- :feature:`60` ``get_ticket_comments`` is now a generator that yields comments and requests each further page only when the caller iterates to it, instead of returning the first page as a list. ``get_ticket_comments_page`` returns one page for callers that page themselves.
- :release:`1.0.0 <1st September 2026>`
- :feature:`55` Add requester identity, tags, group routing, external IDs, and idempotency keys to ``create_ticket``. Requester email and name are now required.
- :feature:`51` Authenticate with the OAuth client credentials grant. ``ZendeskServices`` now takes ``client_id``, ``client_secret``, and ``scope`` instead of ``username`` and ``password``.
- :release:`0.1.0 <27th June 2025>`
- :feature:`-` Initial release
