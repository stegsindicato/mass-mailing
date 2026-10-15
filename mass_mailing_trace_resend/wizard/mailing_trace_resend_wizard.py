from odoo import _, api, fields, models


class MailingTraceResendWizard(models.TransientModel):
    _name = "mailing.trace.resend.wizard"
    _description = "Resend Mailing Traces"

    trace_ids = fields.Many2many(
        "mailing.trace",
        string="Selected traces",
        required=True,
    )
    selected_count = fields.Integer(
        string="Selected traces",
        compute="_compute_counts",
    )
    recipient_count = fields.Integer(
        string="Eligible recipient records",
        compute="_compute_counts",
    )
    mailing_count = fields.Integer(
        string="Mailings",
        compute="_compute_counts",
    )
    draft_mailing_count = fields.Integer(
        string="Mailings currently in draft",
        compute="_compute_counts",
    )
    successful_count = fields.Integer(
        string="Successful deliveries selected",
        compute="_compute_counts",
    )
    duplicate_count = fields.Integer(
        string="Duplicate selections ignored",
        compute="_compute_counts",
    )
    skipped_count = fields.Integer(
        string="Ineligible selections ignored",
        compute="_compute_counts",
    )
    skip_reason_details = fields.Text(
        string="Ignored selection details",
        compute="_compute_counts",
    )

    @api.depends("trace_ids")
    def _compute_counts(self):
        for wizard in self:
            if not wizard.trace_ids:
                wizard.selected_count = 0
                wizard.recipient_count = 0
                wizard.mailing_count = 0
                wizard.draft_mailing_count = 0
                wizard.successful_count = 0
                wizard.duplicate_count = 0
                wizard.skipped_count = 0
                wizard.skip_reason_details = False
                continue

            plan = wizard.trace_ids._get_trace_resend_plan()
            wizard.selected_count = plan["selected_count"]
            wizard.recipient_count = plan["recipient_count"]
            wizard.mailing_count = plan["mailing_count"]
            wizard.draft_mailing_count = len(
                wizard.trace_ids.mapped("mass_mailing_id").filtered(
                    lambda mailing: mailing.state == "draft" and mailing.sent_date
                )
            )
            wizard.successful_count = plan["successful_count"]
            wizard.duplicate_count = plan["duplicate_count"]
            wizard.skipped_count = plan["skipped_count"]
            wizard.skip_reason_details = (
                wizard.trace_ids._format_trace_resend_skip_reasons(plan) or False
            )

    def action_confirm(self):
        self.ensure_one()
        plan = self.trace_ids.action_resend_selected()

        message = _(
            "%(recipients)s recipient record(s) from %(mailings)s mailing(s) "
            "were submitted for resend.",
            recipients=plan["recipient_count"],
            mailings=plan["mailing_count"],
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Trace resend completed"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }
