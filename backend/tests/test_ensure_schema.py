"""Schema repair: legacy tables gain new columns without data loss."""
from __future__ import annotations


def test_repair_adds_missing_columns_and_tables():
    import os

    from sqlalchemy import create_engine, inspect, text

    path = "/tmp/old_schema_test.db"
    try:
        os.remove(path)
    except OSError:
        pass
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE companies (id VARCHAR(36) PRIMARY KEY, "
            "name VARCHAR(200) NOT NULL, autonomy_level INTEGER DEFAULT 2, "
            "created_at DATETIME)"))
        c.execute(text(
            "CREATE TABLE business_profiles (id VARCHAR(36) PRIMARY KEY, "
            "company_id VARCHAR(36), business_name VARCHAR(255) DEFAULT '', "
            "industry VARCHAR(120) DEFAULT '', description TEXT DEFAULT '', "
            "products_services JSON, target_customer TEXT DEFAULT '', "
            "geography VARCHAR(255) DEFAULT '', icp JSON, scoring_rules JSON, "
            "comms_policy JSON, followup_policy JSON, "
            "website_url VARCHAR(500) DEFAULT '', profile_json JSON)"))
        c.execute(text(
            "INSERT INTO companies (id, name) VALUES ('c1', 'Legacy Co')"))

    import app.models.orm  # noqa: F401
    from app.db.ensure_schema import ensure_schema

    added = ensure_schema(eng)
    assert "business_intel_analyses" in added["tables"]
    assert "business_profiles.customer_segments" in added["columns"]

    insp = inspect(eng)
    bp_cols = {col["name"] for col in insp.get_columns("business_profiles")}
    assert {"customer_segments", "business_goals", "enabled_capabilities",
            "working_hours", "timezone"} <= bp_cols
    co_cols = {col["name"] for col in insp.get_columns("companies")}
    assert {"slug", "status", "config", "plan", "updated_at"} <= co_cols

    # Legacy row survives; ORM can read/write it.
    from sqlalchemy.orm import sessionmaker

    from app.models.orm import BusinessProfile, Company

    S = sessionmaker(bind=eng, future=True)
    s = S()
    assert s.get(Company, "c1").name == "Legacy Co"
    bp = BusinessProfile(company_id="c1", business_name="Legacy Co")
    s.add(bp)
    s.commit()
    assert bp.enabled_capabilities == []
    s.close()
    eng.dispose()
