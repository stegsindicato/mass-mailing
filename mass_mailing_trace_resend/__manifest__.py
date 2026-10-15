{
    "name": "Mass Mailing Trace Resend",
    "summary": "Resend selected mass-mailing traces without deleting their history",
    "version": "18.0.1.3.0",
    "category": "Marketing/Email Marketing",
    "author": "STEG",
    "license": "AGPL-3",
    "depends": ["mass_mailing"],
    "data": [
        "security/ir.model.access.csv",
        "views/mailing_trace_views.xml",
        "wizard/mailing_trace_resend_wizard_views.xml",
        "data/mailing_trace_actions.xml",
    ],
    "installable": True,
    "application": False,
}
