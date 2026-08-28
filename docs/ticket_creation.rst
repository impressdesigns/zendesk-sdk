Creating tickets
================

Create a ticket for a requester by supplying their email address and name. Both
are required so Zendesk can create first-time requesters. The initial comment is
sent as public plain text, so requester notifications do not depend on the
Zendesk account's default comment-privacy setting.

.. code-block:: python

   ticket = zendesk.create_ticket(
       "A shipment was returned",
       "Return details\n \nPlease let us know how you would like to proceed.",
       requester_email="customer@example.com",
       requester_name="Customer Name",
       tags=["carrier-return", "rts-1234"],
       external_id="carrier-return:1234",
       idempotency_key="carrier-return:1234",
   )

``group_id`` is optional. Omit it when Zendesk automation routes the ticket by
tag. When an ``idempotency_key`` is supplied, the SDK forwards it in Zendesk's
``Idempotency-Key`` request header.
