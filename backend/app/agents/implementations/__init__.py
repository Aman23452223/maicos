"""Importing this package registers all MVP agents (PRD §10, §33)."""
from app.agents.implementations import (  # noqa: F401
    ai_manager,
    analytics,
    calendar,
    communication,
    customer_support,
    finance,
    hr,
    knowledge,
    marketing,
    project_ops,
    sales_crm,
)

