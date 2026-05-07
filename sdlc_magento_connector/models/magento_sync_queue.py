import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MagentoSyncQueue(models.Model):
    """Persistent queue for webhook events and async sync jobs.

    Webhook controllers enqueue here so the HTTP request returns immediately
    (Magento has a short timeout). A cron consumer drains the queue and
    retries failed jobs with exponential backoff.
    """

    _name = "magento.sync.queue"
    _description = "Magento Sync Queue"
    _order = "scheduled_at asc, id asc"

    EVENT_SELECTION = [
        ("order.placed", "Order Placed"),
        ("order.created", "Order Created"),
        ("order.updated", "Order Updated"),
        ("invoice.created", "Invoice Created"),
        ("creditmemo.created", "Credit Memo Created"),
        ("shipment.created", "Shipment Created"),
        ("stock.updated", "Stock Updated"),
        ("customer.created", "Customer Created"),
        ("customer.updated", "Customer Updated"),
    ]
    STATE_SELECTION = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]
    MAX_RETRIES = 5

    instance_id = fields.Many2one(
        "magento.instance", required=True, ondelete="cascade", index=True
    )
    event = fields.Selection(EVENT_SELECTION, required=True, index=True)
    magento_event_id = fields.Char(
        string="Magento Event ID",
        index=True,
        help="Unique key from Magento (e.g. order entity_id) used for idempotency.",
    )
    payload = fields.Text(string="Raw Payload (JSON)")
    state = fields.Selection(
        STATE_SELECTION, default="pending", required=True, index=True
    )
    retry_count = fields.Integer(default=0)
    last_error = fields.Text()
    source = fields.Selection(
        [("webhook", "Webhook"), ("manual", "Manual"), ("cron", "Cron")],
        default="webhook",
    )
    scheduled_at = fields.Datetime(default=fields.Datetime.now, index=True)
    processed_at = fields.Datetime()

    _sql_constraints = [
        (
            "magento_event_unique",
            "unique(instance_id, event, magento_event_id)",
            "A queue entry already exists for this Magento event.",
        ),
    ]

    # ---------- Public API ----------
    @api.model
    def enqueue(self, instance, event, magento_event_id=None, payload=None, source="webhook"):
        """Idempotent insert. Returns existing record if event_id already seen."""
        domain = [("instance_id", "=", instance.id), ("event", "=", event)]
        if magento_event_id:
            domain.append(("magento_event_id", "=", str(magento_event_id)))
            existing = self.sudo().search(domain, limit=1)
            if existing:
                # Webhook re-delivery — already processed, skip silently.
                return existing
        return self.sudo().create({
            "instance_id": instance.id,
            "event": event,
            "magento_event_id": str(magento_event_id) if magento_event_id else False,
            "payload": json.dumps(payload, default=str) if payload is not None else False,
            "source": source,
        })

    def process(self):
        """Process a single queue entry. Errors set state=failed for retry."""
        self.ensure_one()
        if self.state == "done":
            return True
        self.write({"state": "processing"})
        try:
            payload = json.loads(self.payload) if self.payload else {}
        except ValueError:
            payload = {}

        try:
            self._dispatch(payload)
        except Exception as exc:  # noqa: BLE001 - log and retry
            _logger.exception(
                "Magento queue %s [%s] failed: %s", self.id, self.event, exc
            )
            self.write({
                "state": "failed",
                "last_error": str(exc)[:4000],
                "retry_count": (self.retry_count or 0) + 1,
                "scheduled_at": fields.Datetime.now()
                + timedelta(minutes=min(60, 2 ** (self.retry_count or 0))),
            })
            return False

        self.write({
            "state": "done",
            "processed_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    def _dispatch(self, payload):
        """Route the queue entry to the correct sync method."""
        instance = self.instance_id
        if not instance:
            return
        event = self.event

        if event in ("order.placed", "order.created", "order.updated"):
            order_id = self.magento_event_id or (payload or {}).get("entity_id")
            instance._magento_handle_order_event(order_id, payload)
        elif event == "invoice.created":
            order_id = (payload or {}).get("order_id") or self.magento_event_id
            if order_id:
                instance._magento_handle_order_event(order_id, payload)
        elif event == "creditmemo.created":
            order_id = (payload or {}).get("order_id") or self.magento_event_id
            if order_id:
                instance._magento_handle_credit_memo_event(order_id, payload)
        elif event == "shipment.created":
            order_id = (payload or {}).get("order_id") or self.magento_event_id
            if order_id:
                instance._magento_handle_order_event(order_id, payload)
        elif event == "stock.updated":
            instance._magento_handle_stock_event(payload or {})
        elif event in ("customer.created", "customer.updated"):
            customer_id = self.magento_event_id or (payload or {}).get("id")
            instance._magento_handle_customer_event(customer_id, payload)
        else:
            _logger.warning("Unknown Magento webhook event: %s", event)

    # ---------- Cron entrypoint ----------
    @api.model
    def cron_process_queue(self, batch_size=50):
        now = fields.Datetime.now()
        domain = [
            ("state", "in", ("pending", "failed")),
            ("retry_count", "<", self.MAX_RETRIES),
            ("scheduled_at", "<=", now),
        ]
        records = self.sudo().search(domain, limit=batch_size, order="scheduled_at asc")
        for rec in records:
            try:
                rec.process()
                self.env.cr.commit()  # commit each job so failures don't roll back successes
            except Exception:  # noqa: BLE001
                self.env.cr.rollback()
                _logger.exception("Magento queue cron failure on entry %s", rec.id)
        return True

    def action_retry(self):
        for rec in self:
            rec.write({
                "state": "pending",
                "scheduled_at": fields.Datetime.now(),
                "retry_count": 0,
                "last_error": False,
            })
        return True

    def action_mark_done(self):
        for rec in self:
            rec.write({"state": "done", "processed_at": fields.Datetime.now()})
        return True
