"""CRM providers: internal DB (fully working) + HubSpot (wired, config-gated)."""
from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.leads.normalize import domain_of, norm_email, norm_name
from app.models.orm import CrmActivity, CrmCompany, CrmContact, Lead, Opportunity


class ProviderResult(dict):
    pass


def _not_configured(provider: str, detail: str) -> dict:
    return {"ok": False, "status": "NOT_CONFIGURED",
            "provider": provider, "error": detail}


class CRMProvider(Protocol):
    name: str

    def create_contact(self, db: Session, *, company_id: str,
                       fields: dict[str, Any]) -> dict: ...
    def create_company(self, db: Session, *, company_id: str,
                       fields: dict[str, Any]) -> dict: ...
    def create_opportunity(self, db: Session, *, company_id: str,
                           fields: dict[str, Any]) -> dict: ...
    def add_note(self, db: Session, *, company_id: str,
                 ref: dict[str, Any], note: str) -> dict: ...


class InternalCRMProvider:
    """Postgres-backed MAICOS CRM. Fully working, verified by persistence."""
    name = "internal"

    def create_contact(self, db: Session, *, company_id: str,
                       fields: dict) -> dict:
        email = norm_email(fields.get("email"))
        if email:
            dup = db.query(CrmContact).filter(
                CrmContact.company_id == company_id,
                CrmContact.normalized_email == email).first()
            if dup:
                return {"ok": True, "status": "OK", "deduped": True, "id": dup.id}
        c = CrmContact(
            company_id=company_id, crm_company_id=fields.get("crm_company_id"),
            name=str(fields.get("name", ""))[:255], email=fields.get("email"),
            normalized_email=email, phone=fields.get("phone"),
            role=str(fields.get("role", ""))[:120],
            extra=dict(fields.get("extra") or {}),
        )
        db.add(c)
        db.flush()
        return {"ok": True, "status": "OK", "id": c.id}

    def create_company(self, db: Session, *, company_id: str,
                       fields: dict) -> dict:
        nm = norm_name(fields.get("name"))
        dom = domain_of(fields.get("domain") or fields.get("website"))
        q = db.query(CrmCompany).filter(CrmCompany.company_id == company_id)
        hit = None
        if dom:
            hit = q.filter(CrmCompany.domain == dom).first()
        if not hit and nm:
            hit = q.filter(CrmCompany.normalized_name == nm).first()
        if hit:
            return {"ok": True, "status": "OK", "deduped": True, "id": hit.id}
        c = CrmCompany(
            company_id=company_id, name=str(fields.get("name", ""))[:255],
            normalized_name=nm, domain=dom, website=fields.get("website"),
            industry=str(fields.get("industry", ""))[:120],
            location=str(fields.get("location", ""))[:255],
            extra=dict(fields.get("extra") or {}),
        )
        db.add(c)
        db.flush()
        return {"ok": True, "status": "OK", "id": c.id}

    def create_opportunity(self, db: Session, *, company_id: str,
                           fields: dict) -> dict:
        o = Opportunity(
            company_id=company_id, lead_id=fields.get("lead_id"),
            title=str(fields.get("title", "New Opportunity"))[:255],
            amount=int(fields.get("amount") or 0),
            stage=str(fields.get("stage", "new"))[:80],
            owner=fields.get("owner"), extra=dict(fields.get("extra") or {}),
        )
        db.add(o)
        db.flush()
        return {"ok": True, "status": "OK", "id": o.id}

    def add_note(self, db: Session, *, company_id: str,
                 ref: dict, note: str) -> dict:
        a = CrmActivity(
            company_id=company_id, lead_id=ref.get("lead_id"),
            contact_id=ref.get("contact_id"),
            opportunity_id=ref.get("opportunity_id"),
            kind="note", subject="note", body=note[:4000], created_by="user",
        )
        db.add(a)
        db.flush()
        return {"ok": True, "status": "OK", "id": a.id}


class HubSpotProvider:
    """Wires existing hubspot_crm connector. Never fakes success."""
    name = "hubspot"

    def _creds_ok(self) -> bool:
        import os
        return bool(os.environ.get("HUBSPOT_API_KEY") or os.environ.get("HUBSPOT_TOKEN"))

    def _call(self, operation: str, payload: dict) -> dict:
        if not self._creds_ok():
            return _not_configured("hubspot", "HUBSPOT_API_KEY not configured")
        try:
            from app.integrations.connectors.hubspot_crm import HubSpotCRMConnector
            from app.core.context import Principal
            conn = HubSpotCRMConnector()
            principal = Principal(user_id="system", workspace_id="system", roles=[])
            res = conn.execute(principal, operation, payload)
            if not res.ok or not res.confirmed:
                return {"ok": False, "status": "FAILED",
                        "error": res.message or "hubspot call failed"}
            return {"ok": True, "status": "OK", "data": res.data,
                    "external_id": res.external_id}
        except Exception as exc:
            return {"ok": False, "status": "FAILED", "error": str(exc)[:500]}

    def create_contact(self, db: Session, *, company_id: str, fields: dict) -> dict:
        # persist nothing locally until provider confirms; verify by id
        return self._call("contact.create", fields)

    def create_company(self, db: Session, *, company_id: str, fields: dict) -> dict:
        return self._call("company.upsert", fields)

    def create_opportunity(self, db: Session, *, company_id: str, fields: dict) -> dict:
        return self._call("deal.create", fields)

    def add_note(self, db: Session, *, company_id: str, ref: dict, note: str) -> dict:
        return self._call("activity.record", {**ref, "note": note})


_REGISTRY = {"internal": InternalCRMProvider(), "hubspot": HubSpotProvider()}


def get(name: str):
    if name not in _REGISTRY:
        raise KeyError(f"unknown CRM provider: {name}")
    return _REGISTRY[name]


def convert_lead_to_contact(db: Session, *, company_id: str, lead_id: str,
                            provider: str = "internal") -> dict:
    lead = db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        return {"ok": False, "status": "FAILED", "error": "lead not found"}
    p = get(provider)
    co = p.create_company(db, company_id=company_id, fields={
        "name": lead.company_name, "domain": lead.domain,
        "website": lead.website, "industry": lead.industry,
        "location": lead.location})
    if not co.get("ok"):
        return co
    cc = p.create_contact(db, company_id=company_id, fields={
        "name": lead.company_name, "email": lead.email, "phone": lead.phone,
        "crm_company_id": co.get("id") if provider == "internal" else None})
    if not cc.get("ok"):
        return cc
    if provider == "internal" and cc.get("id"):
        lead.converted_contact_id = cc["id"]
        db.flush()
    return {"ok": True, "status": "OK", "contact_id": cc.get("id"),
            "company_ref": co.get("id")}
