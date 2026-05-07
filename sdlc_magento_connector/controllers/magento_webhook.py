"""HTTP entrypoints for Magento webhooks.

URL pattern:
    POST /magento/webhook/<int:instance_id>/<event>

Magento side must:
  1. Set a shared secret on the instance form (Real-time tab) and copy it
     to the Magento extension config.
  2. Compute HMAC-SHA256(body, secret) and place the hex digest in the
     ``X-Magento-Hmac`` header.
  3. Optionally include ``X-Magento-Event-Id`` for idempotency. If absent,
     we fall back to a payload field (entity_id / id / sku).

Behaviour:
  * Signature mismatch → 401, no work performed.
  * Valid signature → enqueue + 202 Accepted. The cron worker
    ``magento.sync.queue.cron_process_queue`` drains the queue. This keeps
    the HTTP response under Magento's webhook timeout and avoids losing
    events when Odoo is busy.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


VALID_EVENTS = {
    "order.placed",
    "order.created",
    "order.updated",
    "invoice.created",
    "creditmemo.created",
    "shipment.created",
    "stock.updated",
    "customer.created",
    "customer.updated",
}


def _json_response(status, body):
    return request.make_response(
        json.dumps(body),
        status=status,
        headers=[("Content-Type", "application/json")],
    )


class MagentoWebhookController(http.Controller):

    @http.route(
        "/magento/webhook/<int:instance_id>/<string:event>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_event(self, instance_id, event, **_kwargs):
        if event not in VALID_EVENTS:
            return _json_response(400, {"ok": False, "error": "unknown event"})

        instance = (
            request.env["magento.instance"]
            .sudo()
            .browse(instance_id)
            .exists()
        )
        if not instance or not instance.active or not instance.webhook_enabled:
            return _json_response(404, {"ok": False, "error": "instance unavailable"})

        raw_body = request.httprequest.get_data(cache=True) or b""
        received_hmac = (
            request.httprequest.headers.get("X-Magento-Hmac")
            or request.httprequest.headers.get("X-Hub-Signature-256", "")
            .replace("sha256=", "")
        )
        if not instance._verify_webhook_signature(raw_body, received_hmac):
            _logger.warning(
                "Magento webhook signature failed for instance %s event %s",
                instance.id,
                event,
            )
            return _json_response(401, {"ok": False, "error": "bad signature"})

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (UnicodeDecodeError, ValueError):
            return _json_response(400, {"ok": False, "error": "invalid json"})

        magento_event_id = (
            request.httprequest.headers.get("X-Magento-Event-Id")
            or _extract_event_id(event, payload)
        )

        try:
            queue = (
                request.env["magento.sync.queue"]
                .sudo()
                .enqueue(
                    instance,
                    event,
                    magento_event_id=magento_event_id,
                    payload=payload,
                    source="webhook",
                )
            )
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Magento webhook enqueue failed: %s", exc)
            return _json_response(500, {"ok": False, "error": "enqueue failed"})

        # Process inline only when the queue is small — keeps stock/order updates
        # near real-time without exceeding the Magento HTTP timeout.
        if queue.state == "pending":
            try:
                queue.process()
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Magento webhook inline process failed: %s", exc)

        return _json_response(202, {"ok": True, "queue_id": queue.id, "state": queue.state})

    @http.route(
        "/magento/webhook/<int:instance_id>/ping",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def ping(self, instance_id, **_kwargs):
        instance = (
            request.env["magento.instance"]
            .sudo()
            .browse(instance_id)
            .exists()
        )
        if not instance:
            return _json_response(404, {"ok": False})
        return _json_response(
            200,
            {
                "ok": True,
                "instance": instance.name,
                "webhook_enabled": bool(instance.webhook_enabled),
            },
        )


def _extract_event_id(event, payload):
    payload = payload or {}
    if event in ("order.placed", "order.created", "order.updated"):
        return payload.get("entity_id") or payload.get("id") or payload.get("increment_id")
    if event == "invoice.created":
        return payload.get("entity_id") or payload.get("invoice_id")
    if event == "creditmemo.created":
        return payload.get("entity_id") or payload.get("creditmemo_id")
    if event == "shipment.created":
        return payload.get("entity_id") or payload.get("shipment_id")
    if event == "stock.updated":
        sku = payload.get("sku") or ""
        source = payload.get("source_code") or ""
        return f"{sku}:{source}" if sku else None
    if event in ("customer.created", "customer.updated"):
        return payload.get("id") or payload.get("entity_id") or payload.get("email")
    return None
