"""P0/P1 foundation tests: no real credentials required (fake providers only)."""
from __future__ import annotations


def test_crawler_parses_html():
    from app.intel.crawler import parse_html, validate_url

    url = validate_url("example.com")
    assert url.startswith("https://")
    html = ("<html><head><title>Acme Web Studio</title>"
            '<meta name="description" content="We build websites">'
            '</head><body><h1>Web Development</h1>'
            '<p>Contact us at hello@acme.test or +91 98765 43210</p>'
            '<a href="/contact">Contact Us</a>'
            '<a href="https://linkedin.com/company/acme">LinkedIn</a>'
            "</body></html>")
    page = parse_html("https://example.com", html)
    assert "Acme" in page.title
    assert "hello@acme.test" in page.emails
    assert any("linkedin.com" in s for s in page.social_links)


def test_profile_extraction_deterministic():
    from app.intel.crawler import parse_html
    from app.intel.profiles import extract_profile

    page = parse_html("https://example.com",
                      "<html><head><title>Acme</title></head>"
                      "<body><p>We offer website development and mobile app development.</p></body></html>")
    prof = extract_profile([page], "https://example.com")
    assert prof["company_name"]
    assert any("development" in s.lower() for s in prof["services"])


def test_lead_import_dedup_qualify(db, workspace_user):
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects, qualify_lead

    ws = workspace_user["company"].id
    out = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="ABC Foods", email="a@abc.test",
                 location="Nagpur", industry="restaurant", source="csv_import"),
        Prospect(company_name="ABC Foods", email="A@abc.test",
                 location="Nagpur", industry="restaurant", source="csv_import"),
    ])
    assert out["created"] == 1 and out["deduped"] == 1
    lid = out["ids"][0]
    q = qualify_lead(db, company_id=ws, lead_id=lid)
    assert q["ok"] and 0 <= q["score"] <= 100 and q["status"] in (
        "QUALIFIED", "NURTURE", "DISQUALIFIED")


def test_discovery_requires_config():
    from app.leads.providers import get

    res = get("search").discover("restaurants in Nagpur")
    assert res.ok is False and res.status == "NOT_CONFIGURED"
    assert res.prospects == []


def test_crm_internal_verify(db, workspace_user):
    from app.core.verify import verify_crm_record
    from app.crm.providers import get

    ws = workspace_user["company"].id
    p = get("internal")
    co = p.create_company(db, company_id=ws, fields={"name": "ABC"})
    assert co["ok"]
    assert verify_crm_record(db, company_id=ws, kind="company", record_id=co["id"])


def test_hubspot_not_configured_returns_error(db, workspace_user):
    import os
    os.environ.pop("HUBSPOT_API_KEY", None)
    os.environ.pop("HUBSPOT_TOKEN", None)
    from app.crm.providers import get

    ws = workspace_user["company"].id
    out = get("hubspot").create_contact(db, company_id=ws, fields={"name": "x"})
    assert out["ok"] is False and out["status"] == "NOT_CONFIGURED"


def test_email_no_fake_success():
    import os
    os.environ.pop("SENDGRID_API_KEY", None)
    os.environ.pop("SMTP_HOST", None)
    from app.comms.providers import EMAIL

    out = EMAIL.send(to="a@b.test", subject="hi", body="hello")
    assert out["ok"] is False and out["status"] == "NOT_CONFIGURED"


def test_followup_no_duplicates(db, workspace_user):
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects
    from app.scheduling.followups import schedule_sequence

    ws = workspace_user["company"].id
    out = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Dedup Co", email="d@dedup.test")])
    lid = out["ids"][0]
    r1 = schedule_sequence(db, company_id=ws, lead_id=lid)
    r2 = schedule_sequence(db, company_id=ws, lead_id=lid)
    assert r1["created"] > 0 and r2["created"] == 0


def test_response_tracking_stops_followup(db, workspace_user):
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects
    from app.leads.responses import ingest

    ws = workspace_user["company"].id
    out = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Resp Co", email="r@resp.test")])
    lid = out["ids"][0]
    res = ingest(db, company_id=ws, channel="email",
                 from_address="r@resp.test", body="Unsubscribe me please")
    assert res["classification"] == "OPT_OUT"


def test_idempotency_db(db, workspace_user):
    from app.core.idempotency import execute_once

    ws = workspace_user["company"].id
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"ok": True, "v": 1}

    r1 = execute_once(db, company_id=ws, key="k1", payload={"a": 1}, fn=fn)
    r2 = execute_once(db, company_id=ws, key="k1", payload={"a": 1}, fn=fn)
    assert calls["n"] == 1 and r2.get("deduplicated") is True


def test_growth_api_end_to_end(client):
    r = client.post("/api/v1/leads/import", json={
        "prospects": [{"company_name": "API Co", "email": "api@co.test",
                       "location": "Nagpur", "industry": "restaurant"}]})
    assert r.status_code == 200 and r.json()["created"] == 1
    r = client.get("/api/v1/leads")
    assert r.status_code == 200 and len(r.json()) >= 1
    lid = r.json()[0]["id"]
    r = client.post(f"/api/v1/leads/{lid}/qualify")
    assert r.status_code == 200 and "score" in r.json()
    r = client.get("/api/v1/analytics/funnel")
    assert r.status_code == 200 and r.json()["type"] == "actual"
