from odoo import api, fields, models


class MagentoSourceMapping(models.Model):
    """Map a Magento MSI inventory source code to an Odoo warehouse.

    With MSI enabled on Magento, stock lives at the source level (not the
    website level). Stock pushes from Odoo → Magento target a specific
    source via /rest/V1/inventory/source-items, and stock pulls from
    Magento → Odoo update the corresponding Odoo warehouse's quants.
    """

    _name = "magento.source.mapping"
    _description = "Magento MSI Source Mapping"
    _rec_name = "source_code"

    instance_id = fields.Many2one(
        "magento.instance", required=True, ondelete="cascade", index=True
    )
    source_code = fields.Char(required=True, index=True)
    source_name = fields.Char()
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        required=True,
        string="Odoo Warehouse",
        domain="[('company_id', '=', current_company_id)]",
    )
    is_default = fields.Boolean(
        help="Used when Magento payload doesn't reference any source explicitly."
    )
    enabled = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_source_per_instance",
            "unique(instance_id, source_code)",
            "A mapping already exists for this Magento source on this instance.",
        ),
    ]

    @api.model
    def resolve(self, instance, source_code=None):
        if not instance:
            return self.browse()
        domain = [("instance_id", "=", instance.id), ("enabled", "=", True)]
        if source_code:
            mapping = self.sudo().search(
                domain + [("source_code", "=", source_code)], limit=1
            )
            if mapping:
                return mapping
        return self.sudo().search(domain + [("is_default", "=", True)], limit=1)

    @api.constrains("is_default", "instance_id")
    def _check_single_default(self):
        for rec in self.filtered("is_default"):
            other = self.sudo().search(
                [
                    ("instance_id", "=", rec.instance_id.id),
                    ("is_default", "=", True),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if other:
                # Demote previous default silently — admins seldom want two defaults.
                other.with_context(skip_default_demote=True).write({"is_default": False})
