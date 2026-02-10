from odoo import models, fields, api


class MagentoOrderLine(models.Model):
    _name = "magento.order.line"
    _description = "Magento Order Line"

    order_id = fields.Many2one("magento.order", required=True, ondelete="cascade")
    instance_id = fields.Many2one(
        related="order_id.instance_id",
        string="Instance",
        store=True,
        readonly=True,
    )
    magento_item_id = fields.Char(string="Magento Item ID")
    magento_product_id = fields.Many2one(
        "magento.product.map",
        string="Magento Product",
        ondelete="set null",
    )
    sku = fields.Char(string="SKU")
    product_id = fields.Many2one("product.product", string="Product")
    name = fields.Char(string="Description")
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)

    @api.onchange("magento_product_id")
    def _onchange_magento_product_id(self):
        for line in self:
            product_map = line.magento_product_id
            if not product_map:
                continue
            line.sku = product_map.sku or ""
            line.product_id = product_map.odoo_product_id.id if product_map.odoo_product_id else False
            line.name = product_map.name or product_map.sku or ""
            line.price_unit = product_map.price or 0.0
            if not line.quantity:
                line.quantity = 1.0

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            if not line.sku:
                line.sku = line.product_id.default_code or ""
            if not line.name:
                line.name = line.product_id.display_name
            if not line.magento_product_id:
                domain = [("odoo_product_id", "=", line.product_id.id)]
                if line.instance_id:
                    domain.append(("instance_id", "=", line.instance_id.id))
                product_map = self.env["magento.product.map"].search(domain, limit=1)
                if product_map:
                    line.magento_product_id = product_map.id
