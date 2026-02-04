from odoo import models, fields, api


class MagentoOrderLine(models.Model):
    _name = "magento.order.line"
    _description = "Magento Order Line"

    order_id = fields.Many2one("magento.order", required=True, ondelete="cascade")
    magento_item_id = fields.Char(string="Magento Item ID")
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
