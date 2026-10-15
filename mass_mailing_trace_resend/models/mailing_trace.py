from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class MailingTrace(models.Model):
    _inherit = "mailing.trace"

    resend_origin_trace_id = fields.Many2one(
        "mailing.trace",
        string="Resent from",
        readonly=True,
        index=True,
        ondelete="set null",
        copy=False,
        help="Original trace that caused this message to be resent.",
    )
    resend_trace_ids = fields.One2many(
        "mailing.trace",
        "resend_origin_trace_id",
        string="Resent traces",
        readonly=True,
    )

    def _check_trace_resend_access(self):
        if not self.env.user.has_group("mass_mailing.group_mass_mailing_user"):
            raise AccessError(
                _("You do not have permission to resend mass-mailing traces.")
            )

    def _get_trace_resend_plan(self):
        """Build a safe resend plan and explain every rejected selection."""
        self._check_trace_resend_access()
        traces = self.exists()

        in_flight_statuses = {"outgoing", "process", "pending"}
        preliminary = self.env["mailing.trace"]
        skip_reasons = {
            "test_trace": 0,
            "missing_mailing": 0,
            "not_email": 0,
            "mailing_not_sent": 0,
            "model_mismatch": 0,
            "in_flight": 0,
            "missing_res_id": 0,
            "missing_recipient": 0,
        }

        for trace in traces:
            mailing = trace.mass_mailing_id

            # ``is_test_trace`` is not present in all Odoo 18 snapshots.
            # Treat it as an optional compatibility field.
            if (
                "is_test_trace" in trace._fields
                and trace.is_test_trace
            ):
                skip_reasons["test_trace"] += 1
                continue
            if not mailing:
                skip_reasons["missing_mailing"] += 1
                continue
            if trace.trace_type != "mail" or mailing.mailing_type != "mail":
                skip_reasons["not_email"] += 1
                continue
            if not mailing._is_trace_resend_source():
                skip_reasons["mailing_not_sent"] += 1
                continue
            if trace.model != mailing.mailing_model_real:
                skip_reasons["model_mismatch"] += 1
                continue
            if trace.trace_status in in_flight_statuses:
                skip_reasons["in_flight"] += 1
                continue
            if not trace.res_id:
                skip_reasons["missing_res_id"] += 1
                continue

            preliminary |= trace

        # Check record existence in batches, grouped by target model.
        ids_by_model = defaultdict(set)
        for trace in preliminary:
            ids_by_model[trace.model].add(trace.res_id)

        existing_ids_by_model = {}
        for model_name, res_ids in ids_by_model.items():
            try:
                existing_ids_by_model[model_name] = set(
                    self.env[model_name].browse(list(res_ids)).exists().ids
                )
            except KeyError:
                existing_ids_by_model[model_name] = set()

        groups = {}
        duplicate_count = 0
        successful_count = 0
        seen = set()

        # Newest trace wins when the same recipient was selected more than once.
        for trace in preliminary.sorted("id", reverse=True):
            if trace.res_id not in existing_ids_by_model.get(trace.model, set()):
                skip_reasons["missing_recipient"] += 1
                continue

            key = (trace.mass_mailing_id.id, trace.res_id)
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)

            group = groups.setdefault(
                trace.mass_mailing_id.id,
                {
                    "res_ids": [],
                    "trace_ids": [],
                    "origin_by_res_id": {},
                },
            )
            group["res_ids"].append(trace.res_id)
            group["trace_ids"].append(trace.id)
            group["origin_by_res_id"][str(trace.res_id)] = trace.id

            if trace.trace_status in {"sent", "open", "reply"}:
                successful_count += 1

        recipient_count = sum(len(group["res_ids"]) for group in groups.values())
        skipped_count = sum(skip_reasons.values())

        return {
            "groups": groups,
            "selected_count": len(traces),
            "recipient_count": recipient_count,
            "mailing_count": len(groups),
            "duplicate_count": duplicate_count,
            "skipped_count": skipped_count,
            "successful_count": successful_count,
            "skip_reasons": skip_reasons,
        }

    def _format_trace_resend_skip_reasons(self, plan):
        """Return a translated human-readable explanation of rejected traces."""
        reasons = plan.get("skip_reasons", {})
        labels = [
            ("test_trace", _("Test trace: %(count)s")),
            ("missing_mailing", _("Trace without source mailing: %(count)s")),
            ("not_email", _("Not an email mailing/trace: %(count)s")),
            (
                "mailing_not_sent",
                _("Source mailing has not previously been sent: %(count)s"),
            ),
            (
                "model_mismatch",
                _("Recipient model does not match the mailing: %(count)s"),
            ),
            ("in_flight", _("Trace is still being processed: %(count)s")),
            ("missing_res_id", _("Trace has no recipient record ID: %(count)s")),
            (
                "missing_recipient",
                _("Recipient record no longer exists: %(count)s"),
            ),
        ]
        lines = []
        for key, label in labels:
            count = reasons.get(key, 0)
            if count:
                lines.append(label % {"count": count})
        if plan.get("duplicate_count"):
            lines.append(
                _("Duplicate selections collapsed: %(count)s")
                % {"count": plan["duplicate_count"]}
            )
        return "\n".join(lines)

    def action_open_resend_wizard(self):
        self._check_trace_resend_access()
        if not self:
            raise UserError(_("Select at least one mailing trace to resend."))

        plan = self._get_trace_resend_plan()
        if not plan["recipient_count"]:
            details = self._format_trace_resend_skip_reasons(plan)
            message = _(
                "None of the selected traces can be resent."
            )
            if details:
                message += "\n\n" + _("Reason(s):") + "\n" + details
            raise UserError(message)

        return {
            "type": "ir.actions.act_window",
            "name": _("Resend Selected Traces"),
            "res_model": "mailing.trace.resend.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                **self.env.context,
                "default_trace_ids": [(6, 0, self.ids)],
            },
        }

    def action_resend_selected(self):
        """Resend the selected recipient records using their original mailings."""
        self._check_trace_resend_access()
        plan = self._get_trace_resend_plan()

        if not plan["recipient_count"]:
            raise UserError(_("There are no eligible traces to resend."))

        for mailing_id, group in plan["groups"].items():
            mailing = self.env["mailing.mailing"].browse(mailing_id).exists()
            if not mailing:
                continue

            mailing.with_context(
                mailing_trace_resend_trace_ids=group["trace_ids"],
                mailing_trace_resend_origin_by_res_id=group["origin_by_res_id"],
            )._action_resend_mail(group["res_ids"])

        return plan
