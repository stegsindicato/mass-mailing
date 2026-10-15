import re

from odoo import api, fields, models


ENHANCED_STATUS_RE = re.compile(
    r"(?<![\d.])([245]\.\d{1,3}\.\d{1,3})(?![\d.])"
)
SMTP_CODE_RE = re.compile(r"(?<![\d.])([245]\d{2})(?![\d.])")


class MailingTrace(models.Model):
    _inherit = "mailing.trace"

    bounce_smtp_code = fields.Char(
        string="SMTP code",
        compute="_compute_bounce_info",
        store=True,
        index=True,
    )
    bounce_status_code = fields.Char(
        string="Enhanced status code",
        compute="_compute_bounce_info",
        store=True,
        index=True,
    )
    bounce_type = fields.Selection(
        [
            ("soft", "Soft bounce"),
            ("hard", "Hard bounce"),
        ],
        string="Bounce type",
        compute="_compute_bounce_info",
        store=True,
        index=True,
        help="Left empty when the bounce cannot be classified reliably.",
    )
    bounce_reason = fields.Selection(
        [
            ("mailbox_full", "Mailbox full"),
            ("mailbox_disabled", "Mailbox disabled"),
            ("rate_limit", "Rate limit / throttling"),
            ("user_unknown", "Unknown recipient"),
            ("domain_error", "Domain / DNS error"),
            ("spam", "Spam / blocklist rejection"),
            ("content_rejected", "Content rejected"),
            ("temporary_policy", "Temporary policy rejection"),
            ("policy", "Policy rejection"),
            ("server_unavailable", "Server / connection unavailable"),
            ("temporary_failure", "Other temporary failure"),
            ("permanent_failure", "Other permanent failure"),
            ("other", "Other / unknown"),
        ],
        string="Bounce reason",
        compute="_compute_bounce_info",
        store=True,
        index=True,
    )

    @api.depends("trace_status", "failure_type", "failure_reason")
    def _compute_bounce_info(self):
        for trace in self:
            if trace.trace_status != "bounce":
                trace.bounce_smtp_code = False
                trace.bounce_status_code = False
                trace.bounce_type = False
                trace.bounce_reason = False
                continue

            info = trace._parse_bounce_info(trace.failure_reason or "")
            trace.bounce_smtp_code = info["smtp_code"]
            trace.bounce_status_code = info["status_code"]
            trace.bounce_type = info["bounce_type"]
            trace.bounce_reason = info["bounce_reason"]

    @api.model
    def _parse_bounce_info(self, failure_reason):
        text = (failure_reason or "").strip()
        lower = text.lower()

        status_match = ENHANCED_STATUS_RE.search(text)
        smtp_match = SMTP_CODE_RE.search(text)

        status_code = status_match.group(1) if status_match else False
        smtp_code = smtp_match.group(1) if smtp_match else False

        bounce_type = self._classify_bounce_type(lower, smtp_code, status_code)
        bounce_reason = self._classify_bounce_reason(
            lower, bounce_type, status_code
        )

        return {
            "smtp_code": smtp_code,
            "status_code": status_code,
            "bounce_type": bounce_type,
            "bounce_reason": bounce_reason,
        }

    @api.model
    def _classify_bounce_type(self, text, smtp_code=False, status_code=False):
        if status_code:
            if status_code.startswith("4."):
                return "soft"
            if status_code == "5.2.2":
                return "soft"
            if status_code.startswith("5."):
                return "hard"

        if smtp_code:
            if smtp_code.startswith("4"):
                return "soft"
            if smtp_code.startswith("5"):
                return "hard"

        if any(
            value in text
            for value in (
                "temporary",
                "temporarily",
                "try again later",
                "deferred",
                "greylist",
                "rate limit",
                "mailbox full",
                "out of storage space",
                "quota exceeded",
                "service unavailable",
                "connection timed out",
                "connection refused",
            )
        ):
            return "soft"

        if any(
            value in text
            for value in (
                "user unknown",
                "unknown user",
                "no such user",
                "recipient unknown",
                "address does not exist",
                "does not exist",
                "mailbox is disabled",
                "mailbox disabled",
                "account is disabled",
                "account disabled",
                "domain does not exist",
                "no such domain",
            )
        ):
            return "hard"

        return False

    @api.model
    def _classify_bounce_reason(
        self, text, bounce_type=False, status_code=False
    ):
        # Enhanced status code first: it is more reliable than free text.
        if status_code in ("4.2.2", "5.2.2"):
            return "mailbox_full"
        if status_code == "5.1.1":
            return "user_unknown"

        if status_code:
            if status_code.startswith(("4.3.", "4.4.")):
                return "server_unavailable"
            if status_code.startswith("4.7."):
                return "temporary_policy"
            if status_code.startswith("5.1."):
                return "user_unknown"
            if status_code.startswith("5.6."):
                return "content_rejected"
            if status_code.startswith("5.7."):
                return "policy"

        if any(v in text for v in ("mailbox full", "out of storage space", "quota exceeded", "over quota")):
            return "mailbox_full"
        if any(v in text for v in ("mailbox is disabled", "mailbox disabled", "account is disabled", "account disabled")):
            return "mailbox_disabled"
        if any(v in text for v in ("rate limit", "too many messages", "throttl", "temporarily deferred")):
            return "rate_limit"
        if any(v in text for v in ("user unknown", "unknown user", "no such user", "recipient unknown", "does not exist")):
            return "user_unknown"
        if any(v in text for v in ("domain does not exist", "no such domain", "domain not found", "host not found", "dns failure")):
            return "domain_error"
        if any(v in text for v in ("spam", "spamhaus", "spamcop", "blacklist", "blocklist")):
            return "spam"
        if any(v in text for v in ("content rejected", "message content rejected")):
            return "content_rejected"
        if any(v in text for v in ("service unavailable", "server unavailable", "timed out", "connection refused")):
            return "server_unavailable"

        if any(v in text for v in ("policy", "not permitted", "not allowed", "access denied", "relay denied")):
            if bounce_type == "soft":
                return "temporary_policy"
            if bounce_type == "hard":
                return "policy"

        if bounce_type == "soft":
            return "temporary_failure"
        if bounce_type == "hard":
            return "permanent_failure"
        return "other"
