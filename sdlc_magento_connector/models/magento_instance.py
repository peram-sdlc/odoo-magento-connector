from odoo import models, fields
from odoo.exceptions import UserError
from ..services.magento_api import MagentoAPI
import requests


class MagentoInstance(models.Model):
    _name = "magento.instance"
    _description = "Magento Instance"

    # =====================
    # FIELDS
    # =====================
    name = fields.Char(required=True)
    base_url = fields.Char(required=True)
    access_token = fields.Char(required=True)
    active = fields.Boolean(default=True)
    verify_ssl = fields.Boolean(default=True)
    website_id = fields.Integer(string="Magento Website ID")
    store_id = fields.Integer(string="Magento Store ID")
    customer_default_password = fields.Char(string="Magento User Password")
    customer_password_min_length = fields.Integer(
        string="Customer Password Min Length",
        default=8,
    )
    root_category_id = fields.Integer(string="Magento Root Category ID")
    attribute_set_skeleton_id = fields.Integer(
        string="Attribute Set Skeleton ID",
        default=4,
        help="Magento Attribute Set template ID used when creating new sets.",
    )

    sync_product_ids = fields.One2many(
        "magento.product.map", "instance_id", string="Synced Products"
    )
    sync_order_ids = fields.One2many(
        "magento.order", "instance_id", string="Synced Orders"
    )

    # =====================
    # HELPERS
    # =====================
    def _flatten_categories(self, node, parent_id=None):
        items = []
        if not node:
            return items

        items.append({
            "id": node.get("id"),
            "name": node.get("name") or f"Category {node.get('id')}",
            "parent_id": parent_id,
            "children": node.get("children_data") or [],
        })

        for child in node.get("children_data") or []:
            items.extend(self._flatten_categories(child, node.get("id")))

        return items

    # =====================
    # SYNC METHODS
    # =====================
    def sync_categories(self):
        total_created = 0
        total_updated = 0
        for instance in self:
            created = 0
            updated = 0
            api = MagentoAPI(instance)
            try:
                tree = api.get_categories()
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    raise UserError(
                        f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                raise UserError(f"Magento API error: {exc}") from exc

            flat = instance._flatten_categories(tree)
            cat_model = self.env["magento.category"]

            for item in flat:
                if item.get("id") is None:
                    continue

                cat = cat_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_id", "=", str(item["id"])),
                ], limit=1)

                parent = False
                if item.get("parent_id"):
                    parent = cat_model.search([
                        ("instance_id", "=", instance.id),
                        ("magento_id", "=", str(item["parent_id"])),
                    ], limit=1)

                vals = {
                    "name": item.get("name"),
                    "parent_id": parent.id if parent else False,
                }

                if cat:
                    cat.write(vals)
                    updated += 1
                else:
                    vals.update({
                        "instance_id": instance.id,
                        "magento_id": str(item["id"]),
                    })
                    cat_model.create(vals)
                    created += 1
            total_created += created
            total_updated += updated
        return {
            "created": total_created,
            "updated": total_updated,
        }

    def sync_attribute_sets(self):
        total_created = 0
        total_updated = 0
        attr_model = self.env["magento.attribute.set"]
        for instance in self:
            created = 0
            updated = 0
            api = MagentoAPI(instance)
            try:
                sets = api.get_attribute_sets()
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    raise UserError(
                        f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                raise UserError(f"Magento API error: {exc}") from exc

            for item in sets:
                set_id = item.get("attribute_set_id") or item.get("id")
                if set_id is None:
                    continue
                name = (
                    item.get("attribute_set_name")
                    or item.get("name")
                    or f"Attribute Set {set_id}"
                )
                attr_set = attr_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_id", "=", str(set_id)),
                ], limit=1)
                vals = {
                    "name": name,
                    "instance_id": instance.id,
                    "magento_id": str(set_id),
                    "active": True,
                }
                if attr_set:
                    attr_set.with_context(skip_magento_sync=True).write(vals)
                    updated += 1
                else:
                    attr_model.with_context(skip_magento_sync=True).create(vals)
                    created += 1
            total_created += created
            total_updated += updated
        return {
            "created": total_created,
            "updated": total_updated,
        }

    def action_sync_categories(self):
        self.ensure_one()
        start_time = fields.Datetime.now()
        counts = self.sync_categories()
        end_time = fields.Datetime.now()
        total_records = counts.get("created", 0) + counts.get("updated", 0)
        self.env["magento.sync.report"].create({
            "instance_id": self.id,
            "sync_type": "category",
            "mode": "manual",
            "source_action": "manual",
            "total_records": total_records,
            "success": total_records,
            "errors": 0,
            "start_time": start_time,
            "end_time": end_time,
            "categories_created": counts.get("created", 0),
            "categories_updated": counts.get("updated", 0),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Category sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    def action_sync_attribute_sets(self):
        self.ensure_one()
        counts = self.sync_attribute_sets()
        total_records = counts.get("created", 0) + counts.get("updated", 0)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Attribute set sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    def sync_products(self):
        total_created = 0
        total_updated = 0
        total_inventory = 0
        for instance in self:
            created = 0
            updated = 0
            inventory_updated = 0
            api = MagentoAPI(instance)
            try:
                products = api.get_products()
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    raise UserError(
                        f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                raise UserError(f"Magento API error: {exc}") from exc

            map_model = self.env["magento.product.map"]

            for p in products:
                sku = p.get("sku")
                if not sku:
                    continue

                try:
                    product_data = api.get_product(sku)
                except requests.exceptions.HTTPError:
                    continue

                product = self.env["product.product"].search(
                    [("default_code", "=", sku)], limit=1
                )

                if not product:
                    product = self.env["product.product"].create({
                        "name": p.get("name") or sku,
                        "default_code": sku,
                    })

                mapping = map_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_id", "=", str(p.get("id"))),
                ], limit=1)

                if not mapping:
                    mapping = map_model.create({
                        "instance_id": instance.id,
                        "magento_id": str(p.get("id")),
                        "sku": sku,
                        "name": p.get("name"),
                        "odoo_product_id": product.id,
                    })
                    created += 1
                else:
                    updated += 1

                values = mapping._apply_magento_data(product_data)
                values["odoo_product_id"] = product.id
                mapping.with_context(skip_magento_sync=True).write(values)
                stock_item = (product_data.get("extension_attributes") or {}).get("stock_item")
                if stock_item is not None:
                    inventory_updated += 1
            total_created += created
            total_updated += updated
            total_inventory += inventory_updated
        return {
            "created": total_created,
            "updated": total_updated,
            "inventory_updated": total_inventory,
        }

    def action_sync_products(self):
        self.ensure_one()
        start_time = fields.Datetime.now()
        counts = self.sync_products()
        end_time = fields.Datetime.now()
        total_records = counts.get("created", 0) + counts.get("updated", 0)
        self.env["magento.sync.report"].create({
            "instance_id": self.id,
            "sync_type": "product",
            "mode": "manual",
            "source_action": "manual",
            "total_records": total_records,
            "success": total_records,
            "errors": 0,
            "start_time": start_time,
            "end_time": end_time,
            "products_created": counts.get("created", 0),
            "products_updated": counts.get("updated", 0),
            "inventory_updated": counts.get("inventory_updated", 0),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Product sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    def sync_orders(self):
        total_created = 0
        total_updated = 0
        for instance in self:
            created = 0
            updated = 0
            api = MagentoAPI(instance)
            try:
                orders = api.get_orders()
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    raise UserError(
                        f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                raise UserError(f"Magento API error: {exc}") from exc

            order_model = self.env["magento.order"].with_context(skip_magento_sync=True)

            for data in orders:
                magento_id = data.get("entity_id") or data.get("id")
                if not magento_id:
                    continue

                order = order_model.search([
                    ("instance_id", "=", instance.id),
                    ("magento_id", "=", str(magento_id)),
                ], limit=1)

                values = order_model._apply_magento_data(data)
                values["instance_id"] = instance.id

                if order:
                    order.write(values)
                    updated += 1
                else:
                    order_model.create(values)
                    created += 1
            total_created += created
            total_updated += updated
        return {
            "created": total_created,
            "updated": total_updated,
        }

    def action_sync_orders(self):
        self.ensure_one()
        start_time = fields.Datetime.now()
        counts = self.sync_orders()
        end_time = fields.Datetime.now()
        total_records = counts.get("created", 0) + counts.get("updated", 0)
        self.env["magento.sync.report"].create({
            "instance_id": self.id,
            "sync_type": "order",
            "mode": "manual",
            "source_action": "manual",
            "total_records": total_records,
            "success": total_records,
            "errors": 0,
            "start_time": start_time,
            "end_time": end_time,
            "orders_created": counts.get("created", 0),
            "orders_updated": counts.get("updated", 0),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Order sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    def sync_customers(self):
        total_created = 0
        total_updated = 0
        customer_model = self.env["magento.customer"]
        for instance in self:
            created = 0
            updated = 0
            api = MagentoAPI(instance)
            try:
                customers = api.get_customers()
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    raise UserError(
                        f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                raise UserError(f"Magento API error: {exc}") from exc
            for data in customers:
                magento_id = str(data.get("id") or "")
                email = data.get("email") or ""
                customer = False
                if magento_id:
                    customer = customer_model.search([
                        ("instance_id", "=", instance.id),
                        ("magento_id", "=", magento_id),
                    ], limit=1)
                if not customer and email:
                    customer = customer_model.search([
                        ("instance_id", "=", instance.id),
                        ("email", "=", email),
                    ], limit=1)
                values = customer_model._extract_magento_values(data, instance.id)
                if customer:
                    customer.with_context(skip_magento_sync=True).write(values)
                    updated += 1
                else:
                    customer_model.with_context(skip_magento_sync=True).create(values)
                    created += 1
            total_created += created
            total_updated += updated
        return {
            "created": total_created,
            "updated": total_updated,
        }

    def action_sync_customers(self):
        self.ensure_one()
        start_time = fields.Datetime.now()
        counts = self.sync_customers()
        end_time = fields.Datetime.now()
        total_records = counts.get("created", 0) + counts.get("updated", 0)
        self.env["magento.sync.report"].create({
            "instance_id": self.id,
            "sync_type": "customer",
            "mode": "manual",
            "source_action": "manual",
            "total_records": total_records,
            "success": total_records,
            "errors": 0,
            "start_time": start_time,
            "end_time": end_time,
            "customers_created": counts.get("created", 0),
            "customers_updated": counts.get("updated", 0),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Customer sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    def sync_all_and_report(self):
        self.ensure_one()
        start_time = fields.Datetime.now()
        cat_counts = self.sync_categories()
        prod_counts = self.sync_products()
        order_counts = self.sync_orders()
        cust_counts = self.sync_customers()
        end_time = fields.Datetime.now()
        total_records = (
            cat_counts.get("created", 0)
            + cat_counts.get("updated", 0)
            + prod_counts.get("created", 0)
            + prod_counts.get("updated", 0)
            + order_counts.get("created", 0)
            + order_counts.get("updated", 0)
            + cust_counts.get("created", 0)
            + cust_counts.get("updated", 0)
        )
        report_vals = {
            "instance_id": self.id,
            "sync_type": "all",
            "mode": "manual",
            "source_action": "manual",
            "total_records": total_records,
            "success": total_records,
            "errors": 0,
            "start_time": start_time,
            "end_time": end_time,
            "categories_created": cat_counts.get("created", 0),
            "categories_updated": cat_counts.get("updated", 0),
            "products_created": prod_counts.get("created", 0),
            "products_updated": prod_counts.get("updated", 0),
            "orders_created": order_counts.get("created", 0),
            "orders_updated": order_counts.get("updated", 0),
            "customers_created": cust_counts.get("created", 0),
            "customers_updated": cust_counts.get("updated", 0),
            "inventory_updated": prod_counts.get("inventory_updated", 0),
        }
        self.env["magento.sync.report"].create(report_vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Sync",
                "message": f"Sync complete. Total: {total_records}",
                "type": "success",
                "sticky": False,
            },
        }

    # =====================
    # TEST CONNECTION
    # =====================
    def action_test_connection(self):
        self.ensure_one()
        api = MagentoAPI(self)

        try:
            api.get_websites()  # light endpoint
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None:
                raise UserError(
                    f"Magento HTTP {exc.response.status_code}: {exc.response.text}"
                ) from exc
            raise UserError(f"Magento HTTP error: {exc}") from exc
        except Exception as exc:
            raise UserError(f"Connection failed: {exc}") from exc

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Magento Connection",
                "message": "Connection successful.",
                "type": "success",
                "sticky": False,
            },
        }
