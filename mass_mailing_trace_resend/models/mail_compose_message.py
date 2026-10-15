from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _prepare_mail_values_mailing_traces(self, mail_values_all):
        trace_values_all = super()._prepare_mail_values_mailing_traces(
            mail_values_all
        )

        origin_by_res_id = self.env.context.get(
            "mailing_trace_resend_origin_by_res_id"
        )
        if not origin_by_res_id or not self.mass_mailing_id:
            return trace_values_all

        origin_ids = set(origin_by_res_id.values())
        origins = {
            trace.id: trace
            for trace in self.env["mailing.trace"].browse(
                list(origin_ids)
            ).exists()
        }

        for res_id, trace_values in trace_values_all.items():
            if not trace_values:
                continue

            origin_id = origin_by_res_id.get(str(res_id))
            origin = origins.get(origin_id)
            if not origin:
                continue

            if (
                origin.mass_mailing_id == self.mass_mailing_id
                and origin.model == self.model
                and origin.res_id == res_id
            ):
                trace_values["resend_origin_trace_id"] = origin.id

        return trace_values_all
