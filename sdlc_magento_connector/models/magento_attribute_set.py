from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
from ..services.magento_api import MagentoAPI


class MagentoAttributeSet(models.Model):
    _name = "magento.attribute.set"
    _description = "Magento Attribute Set"

    name = fields.Char(required=True)
    magento_id = fields.Char(readonly=True)
    instance_id = fields.Many2one(
        "magento.instance",
        required=True,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.magento_id or self.env.context.get("skip_magento_sync"):
                continue
            api = MagentoAPI(record.instance_id)
            try:
                created = api.create_attribute_set(
                    name=record.name,
                    skeleton_id=record.instance_id.attribute_set_skeleton_id or 4,
                )
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
            magento_id = created.get("attribute_set_id") or created.get("id")
            if not magento_id:
                raise UserError("Magento did not return an Attribute Set ID.")
            record.with_context(skip_magento_sync=True).write({
                "magento_id": str(magento_id),
            })
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_magento_sync"):
            return res
        if "name" not in vals:
            return res
        for record in self:
            if not record.magento_id:
                continue
            api = MagentoAPI(record.instance_id)
            try:
                api.update_attribute_set(record.magento_id, record.name)
            except requests.exceptions.HTTPError as exc:
                record._raise_magento_http_error(exc)
        return res

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
