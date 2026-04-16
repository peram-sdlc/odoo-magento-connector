import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..services.magento_api import MagentoAPI


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    magento_sale_order_id = fields.Many2one(
        "sale.order",
        string="Magento Order",
        related="sale_id",
        store=True,
        readonly=True,
    )
    magento_order_id = fields.Char(
        related="sale_id.magento_order_id",
        store=True,
        readonly=True,
    )
    magento_increment_id = fields.Char(
        string="Order #",
        related="sale_id.magento_increment_id",
        store=True,
        readonly=True,
    )
    magento_sale_order_name = fields.Char(
        related="sale_id.name",
        store=True,
        readonly=True,
    )
    magento_sale_order_date = fields.Datetime(
        string="Order Date",
        compute="_compute_magento_sale_order_date",
        store=True,
        readonly=True,
    )
    magento_ship_to_name = fields.Char(
        string="Ship-to Name",
        compute="_compute_magento_ship_to_name",
        store=True,
        readonly=True,
    )
    magento_total_qty = fields.Float(
        string="Total Quantity",
        compute="_compute_magento_total_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )
    magento_ship_date = fields.Datetime(
        string="Ship Date",
        compute="_compute_magento_ship_date",
        store=True,
        readonly=True,
    )
    magento_customer_email = fields.Char(
        string="Customer Email",
        related="partner_id.email",
        store=True,
        readonly=True,
    )
    magento_customer_phone = fields.Char(
        string="Customer Phone",
        compute="_compute_magento_customer_phone",
        store=True,
        readonly=True,
    )
    magento_shipment_id = fields.Char(
        string="Magento Shipment ID",
        readonly=True,
        copy=False,
    )
    magento_shipment_increment_id = fields.Char(
        string="Magento Shipment #",
        readonly=True,
        copy=False,
    )

    @api.depends("sale_id.magento_created_at", "sale_id.date_order")
    def _compute_magento_sale_order_date(self):
        for picking in self:
            order = picking.sale_id
            picking.magento_sale_order_date = (
                order.magento_created_at or order.date_order or False
            )

    @api.depends("sale_id.partner_shipping_id.name")
    def _compute_magento_ship_to_name(self):
        for picking in self:
            partner = picking.sale_id.partner_shipping_id
            picking.magento_ship_to_name = partner.name if partner else False

    @api.depends(
        "move_ids.product_uom_qty",
        "move_ids.quantity_done",
        "move_ids.state",
        "move_ids.package_level_id",
        "state",
    )
    def _compute_magento_total_qty(self):
        for picking in self:
            qty = 0.0
            for move in picking.move_ids.filtered(lambda m: not m.package_level_id):
                if move.state == "cancel":
                    continue
                if move.quantity_done:
                    qty += move.quantity_done
                else:
                    qty += move.product_uom_qty
            picking.magento_total_qty = qty

    @api.depends("date_done", "scheduled_date")
    def _compute_magento_ship_date(self):
        for picking in self:
            picking.magento_ship_date = picking.date_done or picking.scheduled_date or False

    @api.depends("partner_id.phone", "partner_id.mobile")
    def _compute_magento_customer_phone(self):
        for picking in self:
            partner = picking.partner_id
            picking.magento_customer_phone = (
                (partner.phone or partner.mobile) if partner else False
            )

    def _magento_prepare_shipment_items(self):
        self.ensure_one()
        items = {}
        for move in self.move_ids:
            if move.state == "cancel":
                continue
            sale_line = move.sale_line_id if "sale_line_id" in move._fields else False
            if not sale_line or not sale_line.magento_item_id:
                continue
            qty = float(move.quantity_done or 0.0)
            if qty <= 0:
                qty = float(move.product_uom_qty or 0.0)
            if qty <= 0:
                continue
            key = str(sale_line.magento_item_id)
            items[key] = items.get(key, 0.0) + qty

        payload_items = []
        for item_id, qty in items.items():
            if qty <= 0:
                continue
            try:
                order_item_id = int(item_id)
            except (TypeError, ValueError):
                order_item_id = item_id
            payload_items.append({
                "order_item_id": order_item_id,
                "qty": qty,
            })
        return payload_items

    def _magento_create_shipment(self):
        self.ensure_one()
        if self.magento_shipment_id or self.env.context.get("skip_magento_sync"):
            return False
        if self.picking_type_code != "outgoing" or self.state != "done":
            return False
        order = self.sale_id
        if not order or not order.magento_order_id or not order.magento_instance_id:
            return False
        if order.magento_status in ("complete", "closed", "canceled"):
            _logger.info(
                "Skipping Magento shipment creation for order %s (status=%s).",
                order.name,
                order.magento_status,
            )
            return False

        items = self._magento_prepare_shipment_items()
        if not items:
            _logger.info(
                "Skipping Magento shipment for picking %s: no shippable Magento items.",
                self.name,
            )
            return False

        api = MagentoAPI(order.magento_instance_id)
        payload = {"items": items}
        try:
            result = api.create_shipment(order.magento_order_id, payload)
        except requests.exceptions.HTTPError as exc:
            order._magento_raise_http_error(exc)

        shipment_id = None
        if isinstance(result, dict):
            shipment_id = result.get("entity_id") or result.get("id")
        else:
            shipment_id = result

        if not shipment_id:
            return False

        increment_id = ""
        try:
            shipment_data = api.get_shipment(shipment_id)
            if isinstance(shipment_data, dict):
                increment_id = shipment_data.get("increment_id") or ""
        except requests.exceptions.HTTPError:
            increment_id = ""

        self.write({
            "magento_shipment_id": str(shipment_id),
            "magento_shipment_increment_id": increment_id,
        })
        return True

    def _magento_sync_shipment_after_done(self):
        if self.env.context.get("skip_magento_sync"):
            return
        for picking in self:
            if picking.magento_shipment_id:
                continue
            if picking.picking_type_code != "outgoing" or picking.state != "done":
                continue
            order = picking.sale_id
            if not order or not order.magento_order_id:
                continue
            try:
                picking._magento_create_shipment()
            except UserError as exc:
                picking.message_post(
                    body=_("Magento shipment sync failed: %s") % exc
                )
            except Exception as exc:
                _logger.exception(
                    "Magento shipment sync failed for picking %s: %s",
                    picking.name,
                    exc,
                )

    def _action_done(self):
        res = super()._action_done()
        self._magento_sync_shipment_after_done()
        return res

    def action_push_shipment_to_magento(self):
        self.ensure_one()
        if self.picking_type_code != "outgoing":
            raise UserError(_("Only outgoing deliveries can be pushed to Magento."))
        if self.state != "done":
            raise UserError(_("Please validate the delivery before pushing to Magento."))
        if not self.magento_order_id:
            raise UserError(_("This delivery is not linked to a Magento order."))
        if self.magento_shipment_id:
            raise UserError(_("This delivery is already linked to a Magento shipment."))
        self._magento_create_shipment()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Magento"),
                "message": _("Shipment pushed to Magento."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_magento_shipment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Shipment",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }
