Tickets
=======

Every ticket call is a method on :class:`~zendesk_sdk.client.ZendeskServices`. Build
one as described in :doc:`authentication` first.

Searching
---------

Search returns a list of :class:`~zendesk_sdk.models.Ticket`, optionally narrowed by
status and tag:

.. code-block:: python

   tickets = zendesk.search(
       statuses=["new", "open"],
       tags=["carrier-return"],
   )

Fetching one ticket
-------------------

.. code-block:: python

   ticket = zendesk.get_ticket(12345)

Creating
--------

A ticket needs a subject, a body, and the requester's email address and name. Both
requester fields are required so Zendesk can create first-time requesters.

.. code-block:: python

   ticket = zendesk.create_ticket(
       "A shipment was returned",
       "Return details\n\nPlease let us know how you would like to proceed.",
       requester_email="customer@example.com",
       requester_name="Customer Name",
       email_ccs=["colleague@example.com"],
       tags=["carrier-return", "rts-1234"],
       group_id=42,
       priority="high",
       external_id="carrier-return:1234",
       idempotency_key="carrier-return:1234",
   )

Everything after the requester is optional. Pass an ``idempotency_key`` to make a
retried request return the original ticket instead of filing a duplicate, and
``comment_is_public=False`` to open the ticket with an internal note rather than a
comment the requester is notified about.

``email_ccs`` lists the addresses to copy on the ticket alongside the requester. Zendesk
creates a user for an address it has not seen, allows 48 on a ticket, and ignores them
all when the account has CCs and followers turned off. Whether anyone is emailed is up
to the account's triggers. The addresses are sent as given: the SDK refuses a blank one
or a list longer than 48, and leaves removing duplicates to the caller.

Updating
--------

Set a new status, leave a comment, or both:

.. code-block:: python

   ticket = zendesk.update_ticket(12345, status="solved", comment="Refund issued.")

Comments default to public. Pass ``comment_is_public=False`` to leave an internal
note instead.

To avoid overwriting a change someone else made in the meantime, pass the ticket's
``updated_at`` as ``updated_stamp``. If the ticket has changed since then, Zendesk
rejects the update and the SDK raises
:class:`~zendesk_sdk.exceptions.TicketUpdateConflictError`:

.. code-block:: python

   ticket = zendesk.get_ticket(12345)
   try:
       zendesk.update_ticket(
           ticket.id,
           comment="Cartons received.",
           comment_is_public=False,
           updated_stamp=ticket.updated_at,
       )
   except TicketUpdateConflictError:
       ...  # Re-read the ticket and decide whether to retry.

``updated_stamp`` must be timezone-aware.

Tagging
-------

Adding tags returns the ticket's full tag list:

.. code-block:: python

   tags = zendesk.add_tags_to_ticket(12345, ["rts-1234"])

Tagging a closed ticket raises :class:`~zendesk_sdk.exceptions.TicketClosedError`.

Reading comments
----------------

``get_ticket_comments`` is a generator. It requests the next page of comments
only when you iterate past the current one, so you decide how many to load:

.. code-block:: python

   from itertools import islice

   for comment in zendesk.get_ticket_comments(12345):
       ...

   first_ten = list(islice(zendesk.get_ticket_comments(12345), 10))

To control paging yourself, request one page at a time and pass its
``after_cursor`` back while ``has_more`` is true:

.. code-block:: python

   page = zendesk.get_ticket_comments_page(12345)
   while page.has_more:
       page = zendesk.get_ticket_comments_page(12345, after_cursor=page.after_cursor)

Each :class:`~zendesk_sdk.models.TicketComment` carries its body, whether it was
public, and any attachments. ``plain_body`` is the text alone; ``html_body`` is the comment
as Zendesk formatted it, tables, links and images included.

Reading a ticket's history
--------------------------

A ticket's audits are Zendesk's own record of every update to it: who made the update, when,
and the events it made. ``get_ticket_audits`` is a generator like ``get_ticket_comments``, and
``get_ticket_audits_page`` returns one page for callers that page themselves.

.. code-block:: python

   for audit in sorted(zendesk.get_ticket_audits(12345), key=lambda audit: audit.created_at):
       for event in audit.events:
           if event.type == "Change" and event.field_name == "status":
               print(audit.created_at, audit.author_id, event.previous_value, "->", event.value)

A ``Create`` event set a field as the ticket was opened and a ``Change`` event moved one from
``previous_value`` to ``value``. Values are normally strings, ids included; tags are a list.
Zendesk has many more event types, and each :class:`~zendesk_sdk.models.TicketAuditEvent`
keeps its ``type`` so a caller can pick the ones it reads. An update made by a trigger or an
automation has an ``author_id`` that ``get_users`` does not return. ``metadata`` is Zendesk's
record of where the update came from, passed through as sent; Zendesk does not document its
keys, so read each one as optional.

Audits need the global ``read`` scope. Zendesk refuses them to a token that holds only
``tickets:read``.

Reading what changed
--------------------

The incremental export returns every ticket changed since a time, one page at a time.
Start from a time once, then keep the ``after_cursor`` and pass it on the next call.
``end_of_stream`` means the caller has caught up for now. The export is for admins
only, and Zendesk allows about ten requests a minute.

.. code-block:: python

   page = zendesk.get_incremental_tickets_page(start_time=datetime(2026, 11, 9, tzinfo=UTC))
   while not page.end_of_stream:
       handle(page.tickets)
       page = zendesk.get_incremental_tickets_page(cursor=page.after_cursor)
   handle(page.tickets)
   saved_cursor = page.after_cursor

Deleted tickets, spam among them, are left out unless ``include_deleted=True`` is passed on
every call of the walk; they then come back with the status ``deleted``.

A ticket's comments come from ``get_ticket_comments`` and include each comment's
``author_id`` and ``created_at``. Turn the user ids on tickets and comments into people
with ``get_users``, at most 100 ids per call:

.. code-block:: python

   ids = [user_id for user_id in (ticket.requester_id, *ticket.collaborator_ids) if user_id is not None]
   people = {user.id: user for user in zendesk.get_users(ids)}

A comment's ``attachments`` list each file's name, ``content_type`` and ``size``.
``download_attachment`` returns the bytes. When the account keeps attachments private, the token
needs the ``ticket_attachments:read`` scope:

.. code-block:: python

   for attachment in comment.attachments:
       data = zendesk.download_attachment(attachment)
