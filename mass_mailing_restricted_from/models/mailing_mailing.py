from email.utils import parseaddr
from fnmatch import fnmatch

from odoo import _, models
from odoo.exceptions import AccessError


class MailingMailing(models.Model):
    _inherit = "mailing.mailing"

    _AUTHORIZED_GROUP_XMLID = (
        "mailing_restricted_from.group_restricted_mailing_sender"
    )
    _RESTRICTED_ADDRESSES_PARAM = (
        "mailing_restricted_from.restricted_from_addresses"
    )

    def _extract_email_address(self, value):
        if not value:
            return ""
        _name, email = parseaddr(value)
        return (email or value or "").strip().lower()

    def _get_restricted_from_addresses(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._RESTRICTED_ADDRESSES_PARAM, "")
        )
        return [
            line.strip().lower()
            for line in value.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _from_address_matches_pattern(self, from_address, patterns):
        from_address = (from_address or "").strip().lower()
        for pattern in patterns:
            pattern = (pattern or "").strip().lower()
            if pattern and fnmatch(from_address, pattern):
                return True
        return False

    def _check_restricted_from_permissions(self):
        if self.env.user.has_group(self._AUTHORIZED_GROUP_XMLID):
            return

        restricted_addresses = self._get_restricted_from_addresses()
        if not restricted_addresses:
            return

        for mailing in self:
            from_address = self._extract_email_address(mailing.email_from)
            if self._from_address_matches_pattern(from_address, restricted_addresses):
                raise AccessError(_(
                    "Non tes permisos para enviar emails masivos empregando o enderezo email '%s'."
                ) % from_address)

    def action_put_in_queue(self):
        self._check_restricted_from_permissions()
        return super().action_put_in_queue()