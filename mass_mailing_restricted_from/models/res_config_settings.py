from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mailing_restricted_from_addresses = fields.Text(
        string="Restricted From addresses",
        help=(
            "Una dirección o patrón por línea. "
            "Se aceptan wildcards como '*@steg.gal' o 'marketing+*@steg.gal'. "
            "Los usuarios fuera del grupo autorizado no podrán enviar "
            "mailings usando direcciones que coincidan con estos patrones."
        ),
    )

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res["mailing_restricted_from_addresses"] = icp.get_param(
            "mailing_restricted_from.restricted_from_addresses",
            "",
        )
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "mailing_restricted_from.restricted_from_addresses",
            self.mailing_restricted_from_addresses or "",
        )