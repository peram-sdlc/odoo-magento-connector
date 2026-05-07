from odoo import api, fields, models


class MagentoCustomerGroupMapping(models.Model):
    """Map a Magento customer group to an Odoo pricelist (and optional fiscal position).

    Use cases:
      * Wholesale group → Wholesale pricelist (different per-product prices).
      * Retail group → default Retail pricelist.
    Applied during order import and when sales staff create new orders for
    a Magento customer.
    """

    _name = "magento.customer.group"
    _description = "Magento Customer Group Mapping"
    _rec_name = "magento_group_name"

    instance_id = fields.Many2one(
        "magento.instance", required=True, ondelete="cascade", index=True
    )
    magento_group_id = fields.Char(required=True, index=True)
    magento_group_name = fields.Char(required=True)
    magento_tax_class_id = fields.Char(string="Magento Tax Class ID")
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Odoo Pricelist",
        domain="['|', ('company_id', '=', False), ('company_id', '=', current_company_id)]",
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        domain="['|', ('company_id', '=', False), ('company_id', '=', current_company_id)]",
        help="Optional. Overrides the product tax-class fiscal position when both apply.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_group_per_instance",
            "unique(instance_id, magento_group_id)",
            "A mapping for this Magento customer group already exists.",
        ),
    ]

    @api.model
    def resolve(self, instance, magento_group_id):
        if not instance or magento_group_id in (None, "", False):
            return self.browse()
        return self.sudo().search(
            [
                ("instance_id", "=", instance.id),
                ("magento_group_id", "=", str(magento_group_id)),
                ("active", "=", True),
            ],
            limit=1,
        )
