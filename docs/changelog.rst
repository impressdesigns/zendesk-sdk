Changelog
=========

- :feature:`-` Create public plain-text tickets with requester identity, tags,
  optional group routing, external IDs, and idempotency keys. This changes the
  ``create_ticket`` contract for 0.2.0: callers must pass ``requester_email`` and
  ``requester_name`` by keyword; ``group_id`` is now optional and keyword-only.
- :feature:`51` Authenticate with the OAuth client credentials grant. ``ZendeskServices`` now takes ``client_id``, ``client_secret``, and ``scope`` instead of ``username`` and ``password``.
- :release:`0.1.0 <27th June 2025>`
- :feature:`-` Initial release
