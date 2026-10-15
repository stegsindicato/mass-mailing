import threading

from odoo import _, models
from odoo.exceptions import UserError


class MailingMailing(models.Model):
    _inherit = "mailing.mailing"


    def _is_trace_resend_source(self):
        """Whether this mailing can be used as source for a trace resend.

        Finished mailings are valid. A draft mailing is also valid when it has
        already been sent before (``sent_date`` is set), which is the state
        produced by OCA ``mass_mailing_resend`` after pressing Resend.
        """
        self.ensure_one()
        return (
            self.mailing_type == "mail"
            and (
                self.state == "done"
                or (self.state == "draft" and bool(self.sent_date))
            )
        )

    def _get_seen_list(self):
        """Allow only explicitly selected traces to bypass the seen-list check.

        The normal mass-mailing composer still applies blacklist, opt-out and
        duplicate protections. We only remove the selected source trace emails
        from the mailing's historical seen list.
        """
        seen_list = super()._get_seen_list()

        source_trace_ids = self.env.context.get(
            "mailing_trace_resend_trace_ids"
        )
        if not source_trace_ids:
            return seen_list

        self.ensure_one()
        source_traces = self.env["mailing.trace"].browse(
            source_trace_ids
        ).exists().filtered(
            lambda trace: (
                trace.mass_mailing_id == self
                and trace.trace_type == "mail"
                and trace.model == self.mailing_model_real
            )
        )
        resend_emails = {
            email for email in source_traces.mapped("email") if email
        }
        return seen_list.difference(resend_emails)

    def _action_resend_mail(self, res_ids):
        """Send selected recipient IDs without changing the mailing lifecycle.

        This mirrors Odoo 18's ``_action_send_mail`` composer setup, but does
        not rewrite the original mailing's state, sent date or KPI flags.
        """
        if not res_ids:
            raise UserError(_("There are no recipients selected."))

        author_id = self.env.user.partner_id.id

        for mailing in self:
            if mailing.mailing_type != "mail":
                raise UserError(
                    _("Trace resend currently supports email mailings only.")
                )
            if not mailing._is_trace_resend_source():
                raise UserError(
                    _(
                        "The mailing '%(mailing)s' cannot be used for trace resend. "
                        "Only finished mailings, or previously sent mailings returned "
                        "to draft, can be resent from their traces.",
                        mailing=mailing.display_name,
                    )
                )

            context_user = mailing.user_id or mailing.write_uid or self.env.user
            mailing = mailing.with_context(
                **self.env["res.users"].with_user(context_user).context_get()
            )

            mailing_res_ids = list(dict.fromkeys(res_ids))
            composer_values = {
                "auto_delete": not mailing.keep_archives,
                "auto_delete_keep_log": mailing.reply_to_mode == "update",
                "author_id": author_id,
                "attachment_ids": [
                    (4, attachment.id) for attachment in mailing.attachment_ids
                ],
                "body": mailing._prepend_preview(
                    mailing.body_html or "", mailing.preview
                ),
                "composition_mode": "mass_mail",
                "email_from": mailing.email_from,
                "mail_server_id": mailing.mail_server_id.id,
                "mailing_list_ids": [
                    (4, mailing_list.id)
                    for mailing_list in mailing.contact_list_ids
                ],
                "mass_mailing_id": mailing.id,
                "model": mailing.mailing_model_real,
                "record_name": False,
                "reply_to_force_new": mailing.reply_to_mode == "new",
                "subject": mailing.subject,
                "template_id": False,
            }
            if mailing.reply_to_mode == "new":
                composer_values["reply_to"] = mailing.reply_to

            composer = self.env["mail.compose.message"].with_context(
                active_ids=mailing_res_ids,
                default_composition_mode="mass_mail",
                **mailing._get_mass_mailing_context(),
            ).create(composer_values)

            # Match Odoo's own mass-mailing behavior: commit while sending in
            # normal workers, but not while tests are running.
            auto_commit = not getattr(
                threading.current_thread(), "testing", False
            )
            composer._action_send_mail(auto_commit=auto_commit)

        return True
