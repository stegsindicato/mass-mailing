from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestMailingTraceResend(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({
            "name": "Trace Resend Test",
            "email": "trace-resend@example.org",
        })
        cls.mailing = cls.env["mailing.mailing"].create({
            "subject": "Trace resend test",
            "body_html": "<p>Test</p>",
            "mailing_model_id": cls.env["ir.model"]._get_id("res.partner"),
            "mailing_domain": repr([("id", "=", cls.partner.id)]),
            "state": "done",
        })
        cls.trace = cls.env["mailing.trace"].create({
            "model": "res.partner",
            "res_id": cls.partner.id,
            "email": cls.partner.email,
            "mass_mailing_id": cls.mailing.id,
            "trace_status": "bounce",
            "failure_type": "mail_bounce",
        })

    def test_selected_trace_is_removed_from_seen_list(self):
        self.assertIn(
            self.partner.email,
            self.mailing._get_seen_list(),
        )
        seen_list = self.mailing.with_context(
            mailing_trace_resend_trace_ids=self.trace.ids,
        )._get_seen_list()
        self.assertNotIn(self.partner.email, seen_list)

    def test_plan_deduplicates_same_recipient(self):
        second_trace = self.env["mailing.trace"].create({
            "model": "res.partner",
            "res_id": self.partner.id,
            "email": self.partner.email,
            "mass_mailing_id": self.mailing.id,
            "trace_status": "error",
            "failure_type": "mail_smtp",
        })
        plan = (self.trace | second_trace)._get_trace_resend_plan()

        self.assertEqual(plan["selected_count"], 2)
        self.assertEqual(plan["recipient_count"], 1)
        self.assertEqual(plan["duplicate_count"], 1)
        self.assertEqual(plan["mailing_count"], 1)
        self.assertEqual(
            plan["groups"][self.mailing.id]["trace_ids"],
            [second_trace.id],
        )

    def test_in_flight_trace_is_not_eligible(self):
        trace = self.env["mailing.trace"].create({
            "model": "res.partner",
            "res_id": self.partner.id,
            "email": self.partner.email,
            "mass_mailing_id": self.mailing.id,
            "trace_status": "outgoing",
        })
        plan = trace._get_trace_resend_plan()
        self.assertEqual(plan["recipient_count"], 0)
        self.assertEqual(plan["skipped_count"], 1)


    def test_previously_sent_draft_mailing_is_eligible(self):
        self.mailing.write({
            "state": "draft",
            "sent_date": "2026-09-25 08:00:00",
        })
        plan = self.trace._get_trace_resend_plan()
        self.assertEqual(plan["recipient_count"], 1)
        self.assertEqual(plan["skipped_count"], 0)

    def test_never_sent_draft_mailing_is_not_eligible(self):
        self.mailing.write({
            "state": "draft",
            "sent_date": False,
        })
        plan = self.trace._get_trace_resend_plan()
        self.assertEqual(plan["recipient_count"], 0)
        self.assertEqual(plan["skipped_count"], 1)


    def test_missing_recipient_reason_is_reported(self):
        partner_id = self.partner.id
        self.partner.unlink()
        plan = self.trace._get_trace_resend_plan()
        self.assertEqual(plan["recipient_count"], 0)
        self.assertEqual(plan["skip_reasons"]["missing_recipient"], 1)

    def test_model_mismatch_reason_is_reported(self):
        self.trace.model = "mailing.contact"
        plan = self.trace._get_trace_resend_plan()
        self.assertEqual(plan["recipient_count"], 0)
        self.assertEqual(plan["skip_reasons"]["model_mismatch"], 1)
