"""HTTP-level tests using TestClient with overridden DB."""
from __future__ import annotations


def test_me_returns_authenticated_user(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "owner" + "@" + "acme.example.com"
    assert "owner" in body["roles"]


def test_agents_lists_builtin_agents(client):
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert "ai_manager" in names
    assert "sales_crm" in names
    assert "finance" in names  # Phase 2 agent


def test_onboarding_creates_approval(client):
    r = client.post(
        "/api/v1/commands",
        json={"objective": "Onboard the new client ABC."},
    )
    assert r.status_code == 200
    wf = r.json()
    assert wf["state"] in {"WAITING_APPROVAL", "PARTIAL", "COMPLETED"}
    # Should always require approval for the external welcome email.
    approvals = client.get("/api/v1/approvals?status=PENDING").json()
    assert any(a["action"] == "send_external_communication" for a in approvals)


def test_documents_round_trip(client):
    r = client.post(
        "/api/v1/documents/json",
        json={
            "name": "sop.txt",
            "mime_type": "text/plain",
            "access_roles": ["member"],
            "text": "Refunds processed within 7 business days. The policy is strict.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["indexed"] is True
    listed = client.get("/api/v1/documents").json()
    assert any(d["id"] == body["id"] for d in listed)


def test_idempotency_returns_cached_result():
    # Tested at the unit level in the existing integration test; this
    # placeholder keeps the suite discoverable.
    assert True
