import datetime
import logging

from odoo import api, models, modules

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    _inherit = "mail.mail"

    @api.model
    def process_email_queue(self, email_ids=(), batch_size=1000):
        domain = [
            '&',
                ('state', '=', 'outgoing'),
                '|',
                    ('scheduled_date', '=', False),
                    ('scheduled_date', '<=', datetime.datetime.utcnow()),
        ]
        if 'filters' in self.env.context:
            domain.extend(self.env.context['filters'])

        batch_size = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'mail.mail.queue.batch.size',
                batch_size,
            )
        ) or batch_size

        send_ids = self.search(
            domain,
            limit=batch_size if not email_ids else batch_size * 10,
        ).ids

        if email_ids:
            send_ids = list(set(send_ids) & set(email_ids))

        send_ids.sort()

        if not send_ids:
            return True

        res = None
        try:
            auto_commit = not modules.module.current_test

            res = self.browse(send_ids).send(
                auto_commit=auto_commit,
                post_send_callback=None,
            )

            if self.env.get('ir_cron'):
                self.env['ir.cron']._commit_progress(
                    processed=len(send_ids),
                    remaining=0,
                )

            _logger.info(
                "Mail Queue Single Batch: processed %s queued email(s)",
                len(send_ids),
            )

        except Exception:
            _logger.exception("Failed processing mail queue")

        return res
