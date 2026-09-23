"""Business Intel types + Integrations separation (generic fixtures only)."""
from __future__ import annotations


def _ws(db, email: str, name: str):
    from app.core.security import hash_password
    from app.models.orm import Company, User, WorkspaceMembership

    co = Company(name=name, status="active")
    db.add(co)
    db.flush()
    u = User(company_id=co.id, email=email, name="owner",
             password_hash=hash_password("secret-123"), roles=["owner"])
    db.add(u)
    db.flush()
    db.add(WorkspaceMembership(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    return co, u


def test_intel_types_and_merge(db, monkeypatch):
    from app.intel import service as intel

    pages = [type("P", (), {"url": "https://shop.test/", "title": "Shop",
                            "meta_description": "",
                            "text": "We sell shoes. Offer: 10% off. Open 9am-9pm. Call us.",
                            "emails": [], "phones": [],
                            "social_links": [], "ctas": [],
                            "headings": [], "list_items": [], "links": []})()]
    monkeypatch.setattr(intel, "crawl_site", lambda url: pages)
    monkeypatch.setattr(intel, "llm_enhance", lambda p: p)
    co, _ = _ws(db, "o@biz-a.test", "Biz A")

    mine = intel.analyze_website(db, company_id=co.id, url="https://shop.test/",
                                 analysis_type="my_business")
    assert mine["ok"] and mine["updated"] is False
    prof = mine["profile"]
    assert prof.get("offers") and prof.get("opening_hours")

    comp = intel.analyze_website(db, company_id=co.id, url="https://rival.test/",
                                 analysis_type="competitor")
    assert comp["ok"]
    # competitor must NOT overwrite business profile website
    from app.intel.service import get_or_create_profile
    bp = get_or_create_profile(db, company_id=co.id)
    assert "rival.test" not in (bp.website_url or "")

    again = intel.analyze_website(db, company_id=co.id, url="https://shop.test/",
                                  analysis_type="my_business")
    assert again["updated"] is True and again["version"] == 2

    pros = intel.analyze_website(db, company_id=co.id, url="https://lead.test/",
                                 analysis_type="prospect")
    conv = intel.convert_prospect_to_lead(db, company_id=co.id,
                                          analysis_id=pros["analysis_id"])
    assert conv["ok"] and conv["created"] == 1


def test_intel_tenant_isolation(db, monkeypatch):
    from app.intel import service as intel
    from app.intel.service import list_analyses

    pages = [type("P", (), {"url": "https://x.test/", "title": "X",
                            "meta_description": "",
                            "text": "Services and food menu.",
                            "emails": [], "phones": [],
                            "social_links": [], "ctas": [],
                            "headings": [], "list_items": [], "links": []})()]
    monkeypatch.setattr(intel, "crawl_site", lambda url: pages)
    monkeypatch.setattr(intel, "llm_enhance", lambda p: p)
    co_a, _ = _ws(db, "a@biz.test", "Biz A")
    co_b, _ = _ws(db, "b@biz.test", "Biz B")
    intel.analyze_website(db, company_id=co_a.id, url="https://x.test/")
    assert list_analyses(db, company_id=co_b.id) == []
    assert len(list_analyses(db, company_id=co_a.id)) == 1


def test_integrations_catalog_no_secrets(client):
    r = client.get("/api/v1/integrations/catalog")
    assert r.status_code == 200
    import re
    body = r.text
    # No secret VALUES leak (workspace UUIDs + env var NAMES are fine).
    scrubbed = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "", body, flags=re.IGNORECASE)
    scrubbed = scrubbed.replace("configuration_required", "")
    assert "tvly-dev" not in scrubbed and "tvly-" not in scrubbed.lower()
    assert not re.search(r"[A-Za-z0-9_-]{32,}", scrubbed)
    providers = {i["provider"]: i for i in r.json()["integrations"]}
    assert providers["zomato"]["status"] == "configuration_required"


def test_zomato_connect_honest_and_isolated(client, db, workspace_user):
    r = client.post("/api/v1/integrations/zomato/connect", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "configuration_required"
    # URL is not a credential
    r = client.post("/api/v1/integrations/zomato/connect",
                    json={"url": "https://zomato.com/restaurant/x"})
    assert r.status_code == 400
    # Disconnect works, audited
    r = client.post("/api/v1/integrations/zomato/disconnect")
    assert r.json()["status"] == "disconnected"
    from app.models.orm import AuditLog
    acts = {a.action for a in db.query(AuditLog).filter(
        AuditLog.company_id == workspace_user["company"].id).all()}
    assert "integration.connect" in acts and "integration.disconnect" in acts


def test_command_center_honest_when_disconnected(client):
    r = client.post("/api/v1/commands",
                    json={"objective": "Show today's Zomato orders."})
    assert r.status_code == 200
    wf_id = r.json()["id"]
    tasks = client.get(f"/api/v1/workflows/{wf_id}/tasks").json()
    assert any(t["agent_name"] == "integrations" for t in tasks)
