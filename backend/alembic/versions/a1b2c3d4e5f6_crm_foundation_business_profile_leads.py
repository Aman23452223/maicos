"""crm foundation: business profiles, crm, leads, opportunities, followups

Revision ID: a1b2c3d4e5f6
Revises: fe66d9e32c19
Create Date: 2026-09-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "fe66d9e32c19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), unique=True, index=True),
        sa.Column("business_name", sa.String(255), server_default=""),
        sa.Column("industry", sa.String(120), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("products_services", sa.JSON(), server_default="[]"),
        sa.Column("target_customer", sa.Text(), server_default=""),
        sa.Column("geography", sa.String(255), server_default=""),
        sa.Column("icp", sa.JSON(), server_default="{}"),
        sa.Column("scoring_rules", sa.JSON(), server_default="{}"),
        sa.Column("comms_policy", sa.JSON(), server_default="{}"),
        sa.Column("followup_policy", sa.JSON(), server_default="{}"),
        sa.Column("website_url", sa.String(500), server_default=""),
        sa.Column("profile_json", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "crm_companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("name", sa.String(255), index=True),
        sa.Column("normalized_name", sa.String(255), index=True, server_default=""),
        sa.Column("domain", sa.String(255), index=True, nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("industry", sa.String(120), server_default=""),
        sa.Column("location", sa.String(255), server_default=""),
        sa.Column("external_id", sa.String(255), index=True, nullable=True),
        sa.Column("extra", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_crm_company_ws_norm", "crm_companies", ["company_id", "normalized_name"])
    op.create_index("ix_crm_company_ws_domain", "crm_companies", ["company_id", "domain"])
    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("crm_company_id", sa.String(36), sa.ForeignKey("crm_companies.id"), nullable=True, index=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("normalized_email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("role", sa.String(120), server_default=""),
        sa.Column("external_id", sa.String(255), nullable=True, index=True),
        sa.Column("extra", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_crm_contact_ws_email", "crm_contacts", ["company_id", "normalized_email"])
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("company_name", sa.String(255), server_default="", index=True),
        sa.Column("normalized_name", sa.String(255), server_default="", index=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("normalized_email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("location", sa.String(255), server_default="", index=True),
        sa.Column("industry", sa.String(120), server_default="", index=True),
        sa.Column("source", sa.String(120), server_default="manual", index=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True, index=True),
        sa.Column("enrichment_status", sa.String(40), server_default="pending", index=True),
        sa.Column("status", sa.Enum("NEW", "QUALIFIED", "DISQUALIFIED", "NURTURE", "CONTACTED", "RESPONDED", "MEETING", "PROPOSAL", "WON", "LOST", name="lead_status"), server_default="NEW", index=True),
        sa.Column("score", sa.Integer(), server_default="0", index=True),
        sa.Column("score_version", sa.String(40), server_default="v1"),
        sa.Column("score_reasons", sa.JSON(), server_default="{}"),
        sa.Column("owner", sa.String(120), nullable=True, index=True),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("enriched_json", sa.JSON(), server_default="{}"),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("follow_up_count", sa.Integer(), server_default="0"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("follow_up_status", sa.String(40), server_default="none", index=True),
        sa.Column("preferred_channel", sa.String(40), server_default="email"),
        sa.Column("opted_out", sa.Boolean(), server_default="false", index=True),
        sa.Column("converted_contact_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lead_ws_status_score", "leads", ["company_id", "status", "score"])
    op.create_index("ix_lead_ws_domain", "leads", ["company_id", "domain"])
    op.create_index("ix_lead_ws_followup", "leads", ["company_id", "next_follow_up_at"])
    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=True, index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("amount", sa.Integer(), server_default="0"),
        sa.Column("stage", sa.String(80), server_default="new", index=True),
        sa.Column("status", sa.String(40), server_default="open", index=True),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("expected_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "crm_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=True, index=True),
        sa.Column("contact_id", sa.String(36), nullable=True, index=True),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=True, index=True),
        sa.Column("kind", sa.String(80), server_default="note", index=True),
        sa.Column("subject", sa.String(255), server_default=""),
        sa.Column("body", sa.Text(), server_default=""),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_by", sa.String(120), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), index=True),
        sa.Column("due_at", sa.DateTime(timezone=True), index=True),
        sa.Column("channel", sa.String(40), server_default="email"),
        sa.Column("status", sa.String(40), server_default="scheduled", index=True),
        sa.Column("attempt", sa.Integer(), server_default="0"),
        sa.Column("idempotency_key", sa.String(128), unique=True, index=True),
        sa.Column("result", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=True, index=True),
        sa.Column("channel", sa.String(40), server_default="email", index=True),
        sa.Column("from_address", sa.String(255), server_default=""),
        sa.Column("body", sa.Text(), server_default=""),
        sa.Column("classification", sa.String(60), server_default="UNCLASSIFIED", index=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "proposal_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=True, index=True),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=True, index=True),
        sa.Column("kind", sa.String(60), server_default="proposal", index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("content", sa.Text(), server_default=""),
        sa.Column("status", sa.String(40), server_default="draft", index=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=True, index=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("onboarding_state", sa.String(60), server_default="pending", index=True),
        sa.Column("checklist", sa.JSON(), server_default="[]"),
        sa.Column("extra", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("key", sa.String(128), index=True),
        sa.Column("fingerprint", sa.String(128)),
        sa.Column("result", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_idem_ws_key", "idempotency_keys", ["company_id", "key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_idem_ws_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_table("customers")
    op.drop_table("proposal_documents")
    op.drop_table("inbound_messages")
    op.drop_table("follow_ups")
    op.drop_table("crm_activities")
    op.drop_table("opportunities")
    op.drop_index("ix_lead_ws_followup", table_name="leads")
    op.drop_index("ix_lead_ws_domain", table_name="leads")
    op.drop_index("ix_lead_ws_status_score", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_crm_contact_ws_email", table_name="crm_contacts")
    op.drop_table("crm_contacts")
    op.drop_index("ix_crm_company_ws_domain", table_name="crm_companies")
    op.drop_index("ix_crm_company_ws_norm", table_name="crm_companies")
    op.drop_table("crm_companies")
    op.drop_table("business_profiles")
    try:
        sa.Enum(name="lead_status").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
