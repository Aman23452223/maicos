"""Multi-tenant isolation: two generic businesses, same core (fixtures only)."""
from __future__ import annotations


def _mk(db, email: str, ws_name: str):
    from app.core.security import hash_password
    from app.models.orm import Company, User, WorkspaceMembership

    co = Company(name=ws_name, status="active")
    db.add(co)
    db.flush()
    u = User(company_id=co.id, email=email, name=email.split("@")[0],
             password_hash=hash_password("secret-123"), roles=["owner"])
    db.add(u)
    db.flush()
    db.add(WorkspaceMembership(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    return co, u


def test_cross_workspace_crm_isolation(db):
    from app.crm.providers import get
    from app.models.orm import Lead

    co_a, _ = _mk(db, "a@biz-a.test", "Business A")
    co_b, _ = _mk(db, "b@biz-b.test", "Business B")
    p = get("internal")
    r = p.create_company(db, company_id=co_a.id, fields={"name": "Shared Name"})
    assert r["ok"]
    # Same name in B creates separate row (no cross-tenant dedup leak)
    r2 = p.create_company(db, company_id=co_b.id, fields={"name": "Shared Name"})
    assert r2["ok"] and r2["id"] != r["id"]
    assert db.query(Lead).filter(Lead.company_id == co_b.id).count() == 0


def test_lead_rag_analytics_isolation(db):
    from app.analytics.metrics import funnel
    from app.core.context import Principal
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects
    from app.rag.index import get_index

    co_a, _ = _mk(db, "c@biz-a.test", "Biz A")
    co_b, _ = _mk(db, "d@biz-b.test", "Biz B")
    import_prospects(db, company_id=co_a.id, prospects=[
        Prospect(company_name="Only A", email="x@a.test")])
    pa = Principal(user_id="u", workspace_id=co_a.id, roles=("owner",))
    pb = Principal(user_id="u", workspace_id=co_b.id, roles=("owner",))
    get_index().add(workspace_id=co_a.id, document_id="d1",
                    document_name="doc", text="secret alpha token",
                    access_roles=[])
    assert get_index().search(principal=pb, query="secret alpha") == []
    assert len(get_index().search(principal=pa, query="secret alpha")) >= 1
    fa = funnel(db, company_id=co_a.id)
    fb = funnel(db, company_id=co_b.id)
    assert fa["leads_total"] == 1 and fb["leads_total"] == 0


def test_membership_and_switch(client, db, workspace_user):
    # workspace_user fixture: owner of one workspace
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    lst = client.get("/api/v1/workspaces")
    assert lst.status_code == 200 and len(lst.json()) >= 1
    # Switch to own workspace works
    ws_id = lst.json()[0]["id"]
    r = client.post("/api/v1/auth/switch", json={"workspace_id": ws_id})
    assert r.status_code == 200 and "access_token" in r.json()
    # Switch to unknown workspace forbidden
    r = client.post("/api/v1/auth/switch", json={"workspace_id": "nope"})
    assert r.status_code == 403


def test_cross_workspace_user_creation_forbidden(client, db):
    from app.models.orm import Company
    other = Company(name="Other")
    db.add(other)
    db.commit()
    r = client.post(f"/api/v1/workspaces/{other.id}/users", json={
        "email": "evil@other.example.com", "name": "evil", "password": "secret-123"})
    assert r.status_code == 403
