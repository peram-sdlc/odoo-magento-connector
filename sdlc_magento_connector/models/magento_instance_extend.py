"""Extends magento.instance with the new feature set.

Kept in a separate file so existing instance code stays unchanged. The
features wired here:

* Webhook configuration (token, on/off).
* MSI on/off + source sync.
* Tax class sync.
* Customer group sync.
* Auto-restock toggle for credit memos.
* Webhook event dispatchers used by the queue worker.
"""
import hashlib
import hmac
import logging
import secrets

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.magento_api import MagentoAPI

_logger = logging.getLogger(__name__)


class MagentoInstance(models.Model):
    _inherit = "magento.instance"

    # ---------------- new fields ----------------
    webhook_enabled = fields.Boolean(
        string="Real-time Webhooks",
        default=False,
        help="Accept webhook calls from Magento on /magento/webhook/<id>/<event>.",
    )
    webhook_secret = fields.Char(
        string="Webhook Shared Secret",
        copy=False,
        help="Magento side must HMAC-SHA256 sign the request body with this secret "
             "and send the digest in the X-Magento-Hmac header.",
    )
    msi_enabled = fields.Boolean(
        string="Magento MSI Enabled",
        default=False,
        help="Tick this when the Magento store uses Multi-Source Inventory.",
    )
    auto_restock_on_credit_memo = fields.Boolean(
        string="Auto Restock on Credit Memo",
        default=True,
        help="When a Magento credit memo is imported, reverse the corresponding stock "
             "moves so Odoo inventory matches the refund.",
    )

    tax_mapping_ids = fields.One2many(
        "magento.tax.mapping", "instance_id", string="Tax Class Mappings"
    )
    source_mapping_ids = fields.One2many(
        "magento.source.mapping", "instance_id", string="MSI Source Mappings"
    )
    customer_group_ids = fields.One2many(
        "magento.customer.group", "instance_id", string="Customer Group Mappings"
    )

    # ---------------- webhook helpers ----------------
    def action_generate_webhook_secret(self):
        for instance in self:
            instance.webhook_secret = secrets.token_urlsafe(32)
        return True

    def _verify_webhook_signature(self, raw_body, received_hmac):
        """Constant-time HMAC verification. Empty secret blocks all calls."""
        self.ensure_one()
        if not self.webhook_secret or not received_hmac:
            return False
        digest = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body or b"",
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, received_hmac.strip())

    # ---------------- sync: tax classes ----------------
    def sync_tax_classes(self):
        total_created = 0
        total_updated = 0
        for instance in self:
            api = MagentoAPI(instance)
            try:
                classes = api.get_tax_classes()
            except requests.exceptions.RequestException as exc:
                self._raise_magento_request_user_error(exc, instance)
            tm_model = self.env["magento.tax.mapping"].sudo()
            for cls in classes or []:
                cls_id = str(cls.get("class_id") or "")
                if not cls_id:
                    continue
                existing = tm_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_tax_class_id", "=", cls_id),
                    ("magento_class_type", "=", cls.get("class_type") or "PRODUCT"),
                ], limit=1)
                vals = {
                    "instance_id": instance.id,
                    "magento_tax_class_id": cls_id,
                    "magento_class_name": cls.get("class_name") or f"Class {cls_id}",
                    "magento_class_type": cls.get("class_type") or "PRODUCT",
                }
                if existing:
                    existing.write({"magento_class_name": vals["magento_class_name"]})
                    total_updated += 1
                else:
                    tm_model.create(vals)
                    total_created += 1
        return {"created": total_created, "updated": total_updated}

    def action_sync_tax_classes(self):
        self.ensure_one()
        counts = self.sync_tax_classes()
        return self._magento_notify(
            "Tax Classes",
            f"Created {counts['created']}, updated {counts['updated']} tax classes.",
        )

    # ---------------- sync: MSI sources ----------------
    def sync_inventory_sources(self):
        total_created = 0
        total_updated = 0
        for instance in self:
            if not instance.msi_enabled:
                continue
            api = MagentoAPI(instance)
            try:
                sources = api.get_inventory_sources()
            except requests.exceptions.RequestException as exc:
                self._raise_magento_request_user_error(exc, instance)
            sm_model = self.env["magento.source.mapping"].sudo()
            for src in sources or []:
                code = src.get("source_code") or src.get("name")
                if not code:
                    continue
                existing = sm_model.search([
                    ("instance_id", "=", instance.id),
                    ("source_code", "=", code),
                ], limit=1)
                vals = {
                    "source_name": src.get("name") or code,
                }
                if existing:
                    existing.write(vals)
                    total_updated += 1
                else:
                    vals.update({"instance_id": instance.id, "source_code": code})
                    sm_model.create(vals)
                    total_created += 1
        return {"created": total_created, "updated": total_updated}

    def action_sync_inventory_sources(self):
        self.ensure_one()
        if not self.msi_enabled:
            raise UserError("Enable 'Magento MSI Enabled' before syncing sources.")
        counts = self.sync_inventory_sources()
        return self._magento_notify(
            "MSI Sources",
            f"Created {counts['created']}, updated {counts['updated']} sources. "
            f"Map each to an Odoo warehouse.",
        )

    # ---------------- sync: customer groups ----------------
    def sync_customer_groups(self):
        total_created = 0
        total_updated = 0
        for instance in self:
            api = MagentoAPI(instance)
            try:
                groups = api.get_customer_groups()
            except requests.exceptions.RequestException as exc:
                self._raise_magento_request_user_error(exc, instance)
            gm_model = self.env["magento.customer.group"].sudo()
            for grp in groups or []:
                gid = grp.get("id")
                if gid is None:
                    continue
                existing = gm_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_group_id", "=", str(gid)),
                ], limit=1)
                vals = {
                    "magento_group_name": grp.get("code") or f"Group {gid}",
                    "magento_tax_class_id": (
                        str(grp.get("tax_class_id")) if grp.get("tax_class_id") is not None else False
                    ),
                }
                if existing:
                    existing.write(vals)
                    total_updated += 1
                else:
                    vals.update({"instance_id": instance.id, "magento_group_id": str(gid)})
                    gm_model.create(vals)
                    total_created += 1
        return {"created": total_created, "updated": total_updated}

    def action_sync_customer_groups(self):
        self.ensure_one()
        counts = self.sync_customer_groups()
        return self._magento_notify(
            "Customer Groups",
            f"Created {counts['created']}, updated {counts['updated']} customer groups.",
        )

    # ---------------- webhook event dispatchers ----------------
    def _magento_handle_order_event(self, magento_order_id, payload=None):
        """Pull the order from Magento and run the standard order import."""
        self.ensure_one()
        if not magento_order_id:
            return False
        api = MagentoAPI(self)
        try:
            data = api.get_order(magento_order_id)
        except requests.exceptions.RequestException as exc:
            raise UserError(f"Magento order pull failed for {magento_order_id}: {exc}") from exc
        if not data:
            return False

        order_model = self.env["sale.order"].with_context(skip_magento_sync=True).sudo()
        magento_id = str(data.get("entity_id") or data.get("id") or magento_order_id)
        order = order_model.search([("magento_order_id", "=", magento_id)], limit=1)
        values = order_model._magento_prepare_order_vals(data, self)
        if order:
            order.write(values)
            order._magento_sync_order_lines(data)
        else:
            values.setdefault("user_id", False)
            order = order_model.create(values)
            order._magento_sync_order_lines(data)
        # Follow-on sync (invoices, payments, credit memos, shipments) — same as cron path.
        try:
            if order.magento_invoice_state in ("partial", "invoiced"):
                order._magento_sync_invoices(api)
            if order.magento_payment_state in ("partial", "paid"):
                order._magento_apply_payments_from_magento()
            order._magento_sync_credit_memos(api)
            order._magento_sync_shipments(api)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Post-order sync failed for %s: %s", order.name, exc)
        return order

    def _magento_handle_credit_memo_event(self, magento_order_id, payload=None):
        self.ensure_one()
        if not magento_order_id:
            return False
        order = self.env["sale.order"].sudo().search(
            [("magento_order_id", "=", str(magento_order_id))], limit=1
        )
        if not order:
            # Order doesn't exist in Odoo yet — pull it first.
            order = self._magento_handle_order_event(magento_order_id)
        if not order:
            return False
        api = MagentoAPI(self)
        order._magento_sync_credit_memos(api)
        return True

    def _magento_handle_stock_event(self, payload):
        """Update product map quantity from a stock.updated webhook."""
        self.ensure_one()
        sku = (payload or {}).get("sku")
        if not sku:
            return False
        qty = payload.get("qty")
        try:
            qty = float(qty) if qty is not None else 0.0
        except (TypeError, ValueError):
            qty = 0.0
        is_in_stock = payload.get("is_in_stock")
        source_code = payload.get("source_code")

        map_model = self.env["magento.product.map"].sudo()
        mapping = map_model.search([
            ("instance_id", "=", self.id),
            ("sku", "=", sku),
        ], limit=1)
        if not mapping:
            return False
        vals = {"quantity": qty}
        if is_in_stock is not None:
            vals["stock_status"] = "in_stock" if is_in_stock else "out_of_stock"
        mapping.with_context(skip_magento_sync=True).write(vals)

        # If MSI is on and we know the source, reflect quants in Odoo.
        if self.msi_enabled and source_code and mapping.odoo_product_id:
            src_map = self.env["magento.source.mapping"].resolve(self, source_code)
            warehouse = src_map.warehouse_id if src_map else False
            if warehouse:
                self._magento_update_warehouse_quant(mapping.odoo_product_id, warehouse, qty)
        return True

    def _magento_update_warehouse_quant(self, product, warehouse, qty):
        """Set the on-hand quantity in the warehouse's main stock location.

        Uses stock.quant in inventory_mode (Odoo's supported path for
        absolute on-hand updates).
        """
        if not product or not warehouse:
            return
        location = warehouse.lot_stock_id
        if not location:
            return
        Quant = self.env["stock.quant"].sudo()
        existing = Quant.search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
        ], limit=1)
        vals = {"inventory_quantity": qty}
        if existing:
            existing.with_context(inventory_mode=True).write(vals)
        else:
            Quant.with_context(inventory_mode=True).create({
                "product_id": product.id,
                "location_id": location.id,
                "inventory_quantity": qty,
            })

    def _magento_handle_customer_event(self, magento_customer_id, payload=None):
        self.ensure_one()
        if not magento_customer_id:
            return False
        api = MagentoAPI(self)
        try:
            data = api.get_customer(magento_customer_id)
        except requests.exceptions.RequestException as exc:
            raise UserError(
                f"Magento customer pull failed for {magento_customer_id}: {exc}"
            ) from exc
        if not data:
            return False
        cust_model = self.env["magento.customer"].sudo()
        magento_id = str(data.get("id") or magento_customer_id)
        record = cust_model.search([
            ("instance_id", "=", self.id),
            ("magento_id", "=", magento_id),
        ], limit=1)
        values = cust_model._extract_magento_values(data, self.id)
        if record:
            record.with_context(skip_magento_sync=True).write(values)
        else:
            cust_model.with_context(skip_magento_sync=True).create(values)
        return True

    # ---------------- helpers ----------------
    @api.model
    def _magento_notify(self, title, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": kind,
                "sticky": False,
            },
        }
