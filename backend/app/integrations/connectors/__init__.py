"""Importing this package registers all built-in connectors (PRD §10, §33).

Built-in in-memory connectors are always available. Real provider
adapters register themselves only when their credentials are present
in the environment / secret store.
"""
from app.integrations.connectors import calendar as _calendar  # noqa: F401
from app.integrations.connectors import crm as _crm  # noqa: F401
from app.integrations.connectors import email as _email  # noqa: F401
from app.integrations.connectors.google_calendar import maybe_register as _gcal
from app.integrations.connectors.hubspot_crm import maybe_register as _hs
from app.integrations.connectors.sendgrid_email import maybe_register as _sg

_gcal()
_hs()
_sg()

