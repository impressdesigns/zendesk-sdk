Changelog
=========

- :release:`2.1.0 <9th November 2026>`
- :feature:`72` ``Ticket`` now carries ``subject``, ``description``, ``priority``, ``requester_id``, ``submitter_id``, ``assignee_id``, ``group_id`` and ``collaborator_ids``, and ``TicketComment`` carries ``author_id`` and ``created_at``. All are optional, so existing callers are unaffected.
- :feature:`72` ``get_users`` loads up to 100 users by id in one request, returning the new ``User`` model.
- :feature:`72` ``get_incremental_tickets_page`` returns one page of Zendesk's cursor-based incremental ticket export (``IncrementalTicketPage``). The caller starts from a time, then follows ``after_cursor``. Deleted tickets are left out.
- :release:`2.0.0 <31st October 2026>`
- :feature:`60` ``update_ticket`` takes an optional ``updated_stamp`` for Zendesk safe updates and raises ``TicketUpdateConflictError`` when the ticket changed in the meantime. ``Ticket`` now has ``updated_at``.
- :feature:`60` ``get_ticket_comments`` is now a generator that yields comments and requests each further page only when the caller iterates to it, instead of returning the first page as a list. ``get_ticket_comments_page`` returns one page for callers that page themselves.
- :release:`1.0.0 <1st September 2026>`
- :feature:`55` Add requester identity, tags, group routing, external IDs, and idempotency keys to ``create_ticket``. Requester email and name are now required.
- :feature:`51` Authenticate with the OAuth client credentials grant. ``ZendeskServices`` now takes ``client_id``, ``client_secret``, and ``scope`` instead of ``username`` and ``password``.
- :release:`0.1.0 <27th June 2025>`
- :feature:`-` Initial release
