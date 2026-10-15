=========================
Mass Mailing Trace Resend
=========================

Allows Email Marketing users to select existing ``mailing.trace`` records and
resend the corresponding recipients from the contextual Actions menu.

Main behavior
=============

* The original trace is never deleted.
* A new trace is created for every resend attempt.
* The new trace links back to its source through ``resend_origin_trace_id``.
* Selected traces may belong to several mailings; they are grouped and resent
  with their corresponding original mailing.
* Multiple selected traces for the same mailing and recipient are collapsed
  into one resend.
* Finished mailings can be resent. Previously sent mailings returned to draft by OCA ``mass_mailing_resend`` are also accepted.
* Traces still in outgoing, processing or pending states are not resent.
* Odoo's blacklist, opt-out and current-batch duplicate protections remain
  active.
* The original mailing state and sent date are not changed.

The module is intentionally independent from ``mass_mailing_bounce_info``.
That module can be used to filter soft/hard bounces, while this module only
handles the generic resend operation.

Translations
============

All user-facing labels use standard Odoo translatable Python/XML strings.
A translation template is included in
``i18n/mass_mailing_trace_resend.pot``.


Compatibility with OCA mass_mailing_resend
==========================================

Pressing ``Resend`` in OCA ``mass_mailing_resend`` changes a previously sent
mailing from ``done`` to ``draft`` while preserving ``sent_date``. Such a
mailing is accepted as a trace-resend source. If its subject or body has been
edited while in draft, the current draft content is what will be sent.


Diagnostic rejection reasons
============================

When a selected trace cannot be resent, the module reports the exact reason
(test trace, missing source mailing, wrong model, in-flight status, missing
recipient record, etc.) instead of returning only a generic eligibility error.


Odoo 18 snapshot compatibility
==============================

Some Odoo 18 builds do not yet expose ``mailing.trace.is_test_trace``.
The module treats that field as optional and works with both variants.
