from odoo import api, fields, models


class MagentoTaxMapping(models.Model):
    """Map a Magento tax class to Odoo fiscal position + default tax.

    During order import, the connector resolves the Magento tax_class_id of
    each line item (or the customer group's tax class) and applies the
    matching Odoo fiscal position to the order. The default tax is used as a
    fallback when no order-line tax info comes from Magento.
    """

    _name = "magento.tax.mapping"
    _description = "Magento Tax Class Mapping"
    _rec_name = "magento_class_name"

    instance_id = fields.Many2one(
        "magento.instance", required=True, ondelete="cascade", index=True
    )
    magento_tax_class_id = fields.Char(required=True, index=True)
    magento_class_name = fields.Char(required=True)
    magento_class_type = fields.Selection(
        [("PRODUCT", "Product"), ("CUSTOMER", "Customer")],
        default="PRODUCT",
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Odoo Fiscal Position",
        domain="['|', ('company_id', '=', False), ('company_id', '=', current_company_id)]",
    )
    default_tax_id = fields.Many2one(
        "account.tax",
        string="Default Tax",
        domain="[('type_tax_use', '=', 'sale')]",
        help="Used when Magento doesn't provide line-level tax detail.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_class_per_instance",
            "unique(instance_id, magento_tax_class_id, magento_class_type)",
            "A mapping for this Magento tax class already exists.",
        ),
    ]

    @api.model
    def resolve(self, instance, magento_tax_class_id, class_type="PRODUCT"):
        """Return the active mapping for a class id, or empty recordset."""
        if not instance or not magento_tax_class_id:
            return self.browse()
        return self.sudo().search(
            [
                ("instance_id", "=", instance.id),
                ("magento_tax_class_id", "=", str(magento_tax_class_id)),
                ("magento_class_type", "=", class_type),
                ("active", "=", True),
            ],
            limit=1,
        )
