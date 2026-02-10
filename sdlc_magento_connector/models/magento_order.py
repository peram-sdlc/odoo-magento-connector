import requests
import logging

from odoo import models, fields, api
from odoo.exceptions import UserError
from ..services.magento_api import MagentoAPI


class MagentoOrder(models.Model):
    _name = "magento.order"
    _description = "Magento Order"

    _logger = logging.getLogger(__name__)
    instance_id = fields.Many2one("magento.instance", required=True, ondelete="cascade")
    customer_id = fields.Many2one("res.partner", string="Customer")
    order_line_ids = fields.One2many("magento.order.line", "order_id", string="Order Lines")
    magento_id = fields.Char(string="Magento ID")
    increment_id = fields.Char()
    status = fields.Char()
    grand_total = fields.Float()
    line_total = fields.Float(
        string="Order Total",
        compute="_compute_line_total",
        store=True,
    )
    currency = fields.Char()
    customer_email = fields.Char()
    created_at = fields.Datetime()
    updated_at = fields.Datetime()

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        for rec in self:
            if rec.customer_id and not rec.customer_email:
                rec.customer_email = rec.customer_id.email or ""

    def _extract_billing_address(self, data):
        billing = data.get("billing_address") or {}
        if billing:
            return billing
        addresses = data.get("addresses") or []
        if addresses:
            return addresses[0]
        return {}

    def _resolve_customer(self, data):
        billing = self._extract_billing_address(data)
        email = data.get("customer_email") or billing.get("email") or ""
        firstname = data.get("customer_firstname") or billing.get("firstname") or ""
        lastname = data.get("customer_lastname") or billing.get("lastname") or ""
        name = " ".join([p for p in [firstname, lastname] if p]).strip() or email or ""
        if not email and not name:
            return False

        partner_model = self.env["res.partner"].sudo()
        partner = False
        if email:
            partner = partner_model.search([("email", "=", email)], limit=1)
        if not partner and name:
            partner = partner_model.search([("name", "=", name)], limit=1)
        if partner:
            return partner

        vals = {
            "name": name or email,
            "email": email or False,
        }
        phone = billing.get("telephone") or ""
        if phone:
            vals["phone"] = phone
        street = billing.get("street") or []
        if street:
            vals["street"] = street[0] if len(street) > 0 else ""
            vals["street2"] = street[1] if len(street) > 1 else ""
        city = billing.get("city") or ""
        if city:
            vals["city"] = city
        postcode = billing.get("postcode") or ""
        if postcode:
            vals["zip"] = postcode
        country_code = billing.get("country_id") or ""
        if country_code:
            country = self.env["res.country"].sudo().search(
                [("code", "=", country_code)], limit=1
            )
            if country:
                vals["country_id"] = country.id
        region = billing.get("region") or ""
        if region and "state_id" in partner_model._fields and vals.get("country_id"):
            state = self.env["res.country.state"].sudo().search(
                [("name", "=", region), ("country_id", "=", vals.get("country_id"))],
                limit=1,
            )
            if state:
                vals["state_id"] = state.id
        return partner_model.create(vals)

    @api.depends("order_line_ids.subtotal")
    def _compute_line_total(self):
        for order in self:
            order.line_total = sum(order.order_line_ids.mapped("subtotal"))

    def _split_customer_name(self, partner):
        name = (partner.name or "").strip() if partner else ""
        if not name:
            return "", ""
        parts = name.split()
        firstname = parts[0]
        lastname = " ".join(parts[1:]) if len(parts) > 1 else ""
        return firstname, lastname

    def _build_magento_address(self, partner, address_type):
        if not partner:
            raise UserError("Customer is required to create a Magento order.")
        missing = []
        if not partner.street:
            missing.append("street")
        if not partner.city:
            missing.append("city")
        if not partner.zip:
            missing.append("zip")
        if not partner.country_id:
            missing.append("country")
        if not partner.phone and not partner.mobile:
            missing.append("phone")
        email = partner.email or self.customer_email or ""
        if not email:
            missing.append("email")
        if missing:
            raise UserError(
                "Customer address incomplete. Required: " + ", ".join(missing)
            )
        firstname, lastname = self._split_customer_name(partner)
        street = [partner.street]
        if partner.street2:
            street.append(partner.street2)
        address = {
            "address_type": address_type,
            "firstname": firstname or partner.name or "",
            "lastname": lastname or "",
            "street": street,
            "city": partner.city or "",
            "postcode": partner.zip or "",
            "country_id": partner.country_id.code or "",
            "telephone": partner.phone or partner.mobile or "",
            "email": email,
        }
        if partner.company_name:
            address["company"] = partner.company_name
        if partner.state_id:
            address["region"] = partner.state_id.name or ""
            address["region_code"] = partner.state_id.code or ""
        return address

    def _build_cart_address(self, partner, api=None, include_email=False):
        if not partner:
            raise UserError("Customer is required to create a Magento order.")
        firstname, lastname = self._split_customer_name(partner)
        if not firstname:
            firstname = partner.name or ""
        if not lastname:
            lastname = "Customer"
        missing = []
        if not partner.street:
            missing.append("street")
        if not partner.city:
            missing.append("city")
        if not partner.zip:
            missing.append("zip")
        if not partner.country_id:
            missing.append("country")
        if not partner.phone and not partner.mobile:
            missing.append("phone")
        if include_email and not partner.email and not self.customer_email:
            missing.append("email")
        if missing:
            raise UserError(
                "Customer address incomplete. Required: " + ", ".join(missing)
            )
        street = [partner.street]
        if partner.street2:
            street.append(partner.street2)
        country_code = partner.country_id.code or ""
        address = {
            "firstname": firstname or partner.name or "",
            "lastname": lastname or "",
            "street": street,
            "city": partner.city or "",
            "postcode": partner.zip or "",
            "country_id": country_code,
            "telephone": partner.phone or partner.mobile or "",
        }
        if include_email:
            address["email"] = partner.email or self.customer_email or ""
        if partner.state_id:
            address["region"] = partner.state_id.name or ""
            address["region_code"] = partner.state_id.code or ""
        if api and country_code:
            try:
                country_data = api.get_country(country_code) or {}
            except requests.exceptions.HTTPError as exc:
                country_data = {}
            regions = country_data.get("available_regions") or []
            if regions and not partner.state_id:
                raise UserError(
                    f"State/Region is required for country {country_code}."
                )
            if regions and partner.state_id:
                state_code = (partner.state_id.code or "").upper()
                state_name = (partner.state_id.name or "").lower()
                region_id = None
                for region in regions:
                    code = (region.get("code") or "").upper()
                    name = (region.get("name") or "").lower()
                    if state_code and code == state_code:
                        region_id = region.get("id")
                        break
                    if state_name and name == state_name:
                        region_id = region.get("id")
                        break
                if region_id is not None:
                    address["region_id"] = region_id
        if partner.company_name:
            address["company"] = partner.company_name
        return address

    def _split_shipping_method(self, code):
        if not code:
            return "", ""
        if "_" not in code:
            raise UserError(
                "Default Shipping Method Code must be in 'carrier_method' format (e.g. flatrate_flatrate)."
            )
        carrier, method = code.split("_", 1)
        return carrier, method

    def _create_order_via_cart(self, api):
        self.ensure_one()
        instance = self.instance_id
        if not instance:
            raise UserError("Magento Instance is required.")
        payment_method = instance.default_payment_method or ""
        if not payment_method:
            raise UserError(
                "Set a Default Payment Method Code on the Magento Instance before creating orders."
            )
        shipping_method = instance.default_shipping_method or ""
        if not shipping_method:
            raise UserError(
                "Set a Default Shipping Method Code on the Magento Instance before creating orders."
            )
        carrier_code, method_code = self._split_shipping_method(shipping_method)
        if not carrier_code or not method_code:
            raise UserError(
                "Default Shipping Method Code must be in 'carrier_method' format (e.g. flatrate_flatrate)."
            )

        partner = self.customer_id
        if not partner and self.customer_email:
            partner = self.env["res.partner"].search([("email", "=", self.customer_email)], limit=1)
        if not partner:
            raise UserError("Customer is required to create a Magento order.")
        email = partner.email or self.customer_email or ""
        if not email:
            raise UserError("Customer email is required to create a Magento order.")

        cart_id = api.create_guest_cart()
        for line in self.order_line_ids:
            sku = line.sku or (line.product_id and line.product_id.default_code) or ""
            if not sku:
                raise UserError("Each order line must have a SKU to create a Magento order.")
            qty = float(line.quantity or 0.0)
            if qty <= 0:
                raise UserError("Each order line must have a quantity greater than 0.")
            api.add_guest_cart_item(cart_id, sku, qty)

        shipping_address = self._build_cart_address(partner, api=api, include_email=True)
        billing_address = self._build_cart_address(partner, api=api, include_email=True)
        ship_payload = {
            "addressInformation": {
                "shipping_address": shipping_address,
                "billing_address": billing_address,
                "shipping_method_code": method_code,
                "shipping_carrier_code": carrier_code,
            }
        }
        api.set_guest_shipping_information(cart_id, ship_payload)

        pay_payload = {
            "email": email,
            "paymentMethod": {
                "method": payment_method,
            },
            "billing_address": billing_address,
        }
        order_id = api.set_guest_payment_information(cart_id, pay_payload)
        return api.get_order(order_id)

    def _build_magento_items(self):
        items = []
        for line in self.order_line_ids:
            sku = line.sku or (line.product_id and line.product_id.default_code) or ""
            if not sku:
                raise UserError("Each order line must have a SKU to create a Magento order.")
            item = {
                "sku": sku,
                "name": line.name or sku,
                "qty_ordered": float(line.quantity or 0.0),
                "price": float(line.price_unit or 0.0),
            }
            if line.magento_product_id and line.magento_product_id.magento_id:
                try:
                    item["product_id"] = int(line.magento_product_id.magento_id)
                except (TypeError, ValueError):
                    pass
            items.append(item)
        if not items:
            raise UserError("Order has no lines.")
        return items

    def _build_magento_create_payload(self):
        self.ensure_one()
        instance = self.instance_id
        if not instance:
            raise UserError("Magento Instance is required.")
        payment_method = instance.default_payment_method or ""
        if not payment_method:
            raise UserError(
                "Set a Default Payment Method Code on the Magento Instance before creating orders."
            )
        shipping_method = instance.default_shipping_method or ""
        if not shipping_method:
            raise UserError(
                "Set a Default Shipping Method Code on the Magento Instance before creating orders."
            )

        partner = self.customer_id
        if not partner and self.customer_email:
            partner = self.env["res.partner"].search([("email", "=", self.customer_email)], limit=1)
        if not partner:
            raise UserError("Customer is required to create a Magento order.")

        billing_address = self._build_magento_address(partner, "billing")
        shipping_address = self._build_magento_address(partner, "shipping")
        firstname, lastname = self._split_customer_name(partner)

        items = self._build_magento_items()
        entity = {
            "customer_email": partner.email or self.customer_email or "",
            "customer_firstname": firstname or partner.name or "",
            "customer_lastname": lastname or "",
            "billing_address": billing_address,
            "items": items,
            "payment": {"method": payment_method},
            "extension_attributes": {
                "shipping_assignments": [
                    {
                        "shipping": {
                            "address": shipping_address,
                            "method": shipping_method,
                            "total": {
                                "shipping_amount": float(instance.default_shipping_amount or 0.0),
                                "base_shipping_amount": float(instance.default_shipping_amount or 0.0),
                                "shipping_description": instance.default_shipping_description or shipping_method,
                            },
                        },
                        "items": items,
                    }
                ]
            },
        }
        if instance.store_id:
            entity["store_id"] = int(instance.store_id)
        if self.currency:
            entity["order_currency_code"] = self.currency
        return {"entity": entity}

    def _build_magento_update_payload(self):
        self.ensure_one()
        customer_email = self.customer_email or (self.customer_id.email if self.customer_id else "") or ""
        payload = {}
        if self.status:
            payload["status"] = self.status
        if customer_email:
            payload["customer_email"] = customer_email
        if self.currency:
            payload["order_currency_code"] = self.currency
        return {"entity": payload} if payload else None

    def _drop_unsupported_field(self, payload, field_name):
        entity = (payload or {}).get("entity") or {}
        if not entity or not field_name:
            return False
        target = field_name.replace("_", "").lower()
        for key in list(entity.keys()):
            if key.replace("_", "").lower() == target:
                entity.pop(key, None)
                return True
        return False

    def _update_magento_order(self, api, payload):
        self.ensure_one()
        if not payload or not payload.get("entity"):
            return None
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                return api.update_order(self.magento_id, payload)
            except requests.exceptions.HTTPError as exc:
                response = exc.response
                if response is not None and response.status_code == 400:
                    message = ""
                    params = {}
                    try:
                        data = response.json()
                        message = data.get("message") or response.text
                        params = data.get("parameters") or {}
                    except Exception:
                        message = response.text
                    if "is not supported" in (message or ""):
                        field_name = params.get("fieldName") if isinstance(params, dict) else ""
                        dropped = self._drop_unsupported_field(payload, field_name or "")
                        if dropped and payload.get("entity"):
                            self._logger.warning(
                                "Magento order update retry without unsupported field '%s' (id=%s).",
                                field_name,
                                self.magento_id,
                            )
                            continue
                        self._logger.warning(
                            "Magento order update skipped due to unsupported field '%s' (id=%s).",
                            field_name,
                            self.magento_id,
                        )
                        return None
                self._raise_magento_http_error(exc)
        return None

    def _apply_magento_data(self, data):
        customer_email = data.get("customer_email") or self._extract_billing_address(data).get("email") or ""
        customer = self._resolve_customer(data)
        return {
            "magento_id": str(data.get("entity_id") or data.get("id") or ""),
            "increment_id": data.get("increment_id") or "",
            "status": data.get("status") or "",
            "grand_total": float(data.get("grand_total") or 0.0),
            "currency": data.get("order_currency_code") or data.get("base_currency_code") or "",
            "customer_email": customer_email,
            **({"customer_id": customer.id} if customer else {}),
            "created_at": data.get("created_at") or False,
            "updated_at": data.get("updated_at") or False,
        }

    def _prepare_order_line_vals(self, item):
        self.ensure_one()
        sku = item.get("sku") or ""
        product = False
        product_map = False
        magento_product_id = item.get("product_id")
        map_model = self.env["magento.product.map"].sudo()
        if self.instance_id:
            if magento_product_id:
                product_map = map_model.search([
                    ("instance_id", "=", self.instance_id.id),
                    ("magento_id", "=", str(magento_product_id)),
                ], limit=1)
            if not product_map and sku:
                product_map = map_model.search([
                    ("instance_id", "=", self.instance_id.id),
                    ("sku", "=", sku),
                ], limit=1)
        elif sku:
            product_map = map_model.search([("sku", "=", sku)], limit=1)
        if product_map and product_map.odoo_product_id:
            product = product_map.odoo_product_id
        elif sku:
            product = self.env["product.product"].sudo().search(
                [("default_code", "=", sku)], limit=1
            )
        return {
            "magento_item_id": str(item.get("item_id") or ""),
            "sku": sku,
            "magento_product_id": product_map.id if product_map else False,
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
            params = payload.get("parameters")
            if params:
                message = f"{message} | parameters={params}"
        except Exception:
            message = response.text
        status = response.status_code
        raise UserError(f"Magento API error ({status}): {message}") from exc

    def _refresh_from_magento(self, api, magento_id):
        self.ensure_one()
        if not magento_id:
            return
        try:
            data = api.get_order(magento_id)
        except requests.exceptions.HTTPError as exc:
            self._raise_magento_http_error(exc)
        values = self._apply_magento_data(data)
        self.with_context(skip_magento_sync=True).write(values)
        self._sync_order_lines(data)

    def action_create_magento_order(self):
        for record in self:
            api = MagentoAPI(record.instance_id)
            try:
                response = record._create_order_via_cart(api)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            if isinstance(response, dict):
                values = record._apply_magento_data(response)
                record.with_context(skip_magento_sync=True).write(values)
                if not response.get("increment_id") or not response.get("items"):
                    record._refresh_from_magento(api, values.get("magento_id"))

    def action_update_magento_order(self):
        for record in self:
            if not record.magento_id:
                raise UserError("Magento ID is required to update an order in Magento.")
            api = MagentoAPI(record.instance_id)
            payload = record._build_magento_update_payload()
            try:
                response = record._update_magento_order(api, payload)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            if isinstance(response, dict):
                values = record._apply_magento_data(response)
                record.with_context(skip_magento_sync=True).write(values)
                if not response.get("increment_id") or not response.get("items"):
                    record._refresh_from_magento(api, record.magento_id)

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
            try:
                if record.magento_id:
                    payload = record._build_magento_update_payload()
                    response = record._update_magento_order(api, payload)
                else:
                    response = record._create_order_via_cart(api)
                if isinstance(response, dict):
                    values = record._apply_magento_data(response)
                    record.with_context(skip_magento_sync=True).write(values)
                    record._sync_order_lines(response)
                    if not response.get("increment_id") or not response.get("items"):
                        record._refresh_from_magento(api, values.get("magento_id"))
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
            try:
                response = record._create_order_via_cart(api)
                if isinstance(response, dict):
                    values = record._apply_magento_data(response)
                    record.with_context(skip_magento_sync=True).write(values)
                    record._sync_order_lines(response)
                    if not response.get("increment_id") or not response.get("items"):
                        record._refresh_from_magento(api, values.get("magento_id"))
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
        return records
