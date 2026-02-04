from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
from ..services.magento_api import MagentoAPI


class MagentoOrder(models.Model):
    _name = "magento.order"
    _description = "Magento Order"

    instance_id = fields.Many2one("magento.instance", required=True, ondelete="cascade")
    customer_id = fields.Many2one("res.partner", string="Customer")
    order_line_ids = fields.One2many("magento.order.line", "order_id", string="Order Lines")
    magento_id = fields.Char(string="Magento ID")
    increment_id = fields.Char()
    status = fields.Char()
    grand_total = fields.Float()
    currency = fields.Char()
    customer_email = fields.Char()
    created_at = fields.Datetime()
    updated_at = fields.Datetime()

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        for rec in self:
            if rec.customer_id and not rec.customer_email:
                rec.customer_email = rec.customer_id.email or ""

    def _build_magento_payload(self):
        self.ensure_one()
        customer_email = self.customer_email or (self.customer_id.email if self.customer_id else "") or ""
        payload = {
            "entity_id": self.magento_id or None,
            "increment_id": self.increment_id or "",
            "status": self.status or "",
            "grand_total": float(self.grand_total or 0.0),
            "order_currency_code": self.currency or "",
            "customer_email": customer_email,
        }
        if self.created_at:
            payload["created_at"] = fields.Datetime.to_string(self.created_at)
        if self.updated_at:
            payload["updated_at"] = fields.Datetime.to_string(self.updated_at)
        return {"entity": payload}

    def _apply_magento_data(self, data):
        return {
            "magento_id": str(data.get("entity_id") or data.get("id") or ""),
            "increment_id": data.get("increment_id") or "",
            "status": data.get("status") or "",
            "grand_total": float(data.get("grand_total") or 0.0),
            "currency": data.get("order_currency_code") or data.get("base_currency_code") or "",
            "customer_email": data.get("customer_email") or "",
            "created_at": data.get("created_at") or False,
            "updated_at": data.get("updated_at") or False,
        }

    def _prepare_order_line_vals(self, item):
        sku = item.get("sku") or ""
        product = False
        if sku:
            product = self.env["product.product"].sudo().search(
                [("default_code", "=", sku)], limit=1
            )
        return {
            "magento_item_id": str(item.get("item_id") or ""),
            "sku": sku,
            "product_id": product.id if product else False,
            "name": item.get("name") or sku or "",
            "quantity": float(item.get("qty_ordered") or item.get("qty") or 0.0),
            "price_unit": float(item.get("price") or 0.0),
        }

    def _sync_order_lines(self, data):
        self.ensure_one()
        items = data.get("items") or []
        if not items:
            return
        # Replace existing lines with latest Magento items.
        self.order_line_ids.unlink()
        line_vals = []
        for item in items:
            line_vals.append((0, 0, self._prepare_order_line_vals(item)))
        if line_vals:
            self.with_context(skip_magento_sync=True).write({"order_line_ids": line_vals})

    def _raise_magento_http_error(self, exc):
        response = exc.response
        if response is None:
            raise UserError(f"Magento API error: {exc}") from exc
        try:
            payload = response.json()
            message = payload.get("message") or response.text
        except Exception:
            message = response.text
        status = response.status_code
        raise UserError(f"Magento API error ({status}): {message}") from exc

    def action_create_magento_order(self):
        for record in self:
            api = MagentoAPI(record.instance_id)
            payload = record._build_magento_payload()
            try:
                response = api.create_order(payload)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            if isinstance(response, dict):
                values = record._apply_magento_data(response)
                record.with_context(skip_magento_sync=True).write(values)

    def action_update_magento_order(self):
        for record in self:
            if not record.magento_id:
                raise UserError("Magento ID is required to update an order in Magento.")
            api = MagentoAPI(record.instance_id)
            payload = record._build_magento_payload()
            try:
                response = api.update_order(record.magento_id, payload)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            if isinstance(response, dict):
                values = record._apply_magento_data(response)
                record.with_context(skip_magento_sync=True).write(values)

    def action_pull_magento_order(self):
        for record in self:
            if not record.magento_id:
                raise UserError("Magento ID is required to pull order from Magento.")
            api = MagentoAPI(record.instance_id)
            try:
                data = api.get_order(record.magento_id)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            values = record._apply_magento_data(data)
            record.with_context(skip_magento_sync=True).write(values)
            record._sync_order_lines(data)

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_magento_sync"):
            return res
        for record in self:
            if not record.instance_id:
                continue
            api = MagentoAPI(record.instance_id)
            payload = record._build_magento_payload()
            try:
                if record.magento_id:
                    response = api.update_order(record.magento_id, payload)
                else:
                    response = api.create_order(payload)
                if isinstance(response, dict):
                    values = record._apply_magento_data(response)
                    record.with_context(skip_magento_sync=True).write(values)
                    record._sync_order_lines(response)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
        return res

    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_magento_sync"):
            return records
        for record in records:
            if not record.instance_id or record.magento_id:
                continue
            api = MagentoAPI(record.instance_id)
            payload = record._build_magento_payload()
            try:
                response = api.create_order(payload)
                if isinstance(response, dict):
                    values = record._apply_magento_data(response)
                    record.with_context(skip_magento_sync=True).write(values)
                    record._sync_order_lines(response)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
        return records
