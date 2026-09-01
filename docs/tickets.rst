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
retried request return the original ticket instead of filing a duplicate.

Updating
--------

Set a new status, leave a comment, or both:

.. code-block:: python

   ticket = zendesk.update_ticket(12345, status="solved", comment="Refund issued.")

Comments default to public. Pass ``comment_is_public=False`` to leave an internal
note instead.

Tagging
-------

Adding tags returns the ticket's full tag list:

.. code-block:: python

   tags = zendesk.add_tags_to_ticket(12345, ["rts-1234"])

Tagging a closed ticket raises :class:`~zendesk_sdk.exceptions.TicketClosedError`.

Reading comments
----------------

.. code-block:: python

   comments = zendesk.get_ticket_comments(12345)

Each :class:`~zendesk_sdk.models.TicketComment` carries its body, whether it was
public, and any attachments.
