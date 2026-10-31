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
public, and any attachments.
