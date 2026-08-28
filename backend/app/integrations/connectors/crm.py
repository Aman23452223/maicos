"""CRM connector (file-backed local store).

The connector interface is identical to a real HubSpot/Salesforce
adapter. The only difference is that "external system" persistence is
a JSON file on disk so the system can be observed and restarted
without losing state. Swap in the HubSpot adapter in
`connectors/hubspot_crm.py` to talk to a real CRM.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.core.context import Principal
from app.integrations.base import ToolResult, register
from app.integrations.store import JsonStore, stores_root

_CONTACTS = JsonStore[dict[str, Any]](stores_root() / "crm.contacts.json")
_COMPANIES = JsonStore[dict[str, Any]](stores_root() / "crm.companies.json")
_DEALS = JsonStore[dict[str, Any]](stores_root() / "crm.deals.json")
_ACTIVITIES = JsonStore[dict[str, Any]](stores_root() / "crm.activities.json")


class CRMConnector:
    name = "crm"

    def operations(self) -> list[str]:
        return [
            "contact.create",
            "contact.update",
            "contact.get",
            "contact.list",
            "company.upsert",
            "deal.create",
            "deal.update_stage",
            "deal.list",
            "activity.record",
        ]

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        if operation == "contact.create":
            cid = str(uuid.uuid4())
            rec = {
                "id": cid,
                "workspace_id": principal.workspace_id,
                **payload,
            }
            _CONTACTS.put(cid, rec)
            return ToolResult(ok=True, confirmed=True, data=rec, external_id=cid,
                              message="persisted to crm.contacts.json")
        if operation == "contact.update":
            cid_raw = payload.get("id")
            cid_lookup = cid_raw if isinstance(cid_raw, str) else None
            if not cid_lookup or not _CONTACTS.get(cid_lookup):
                return ToolResult(ok=False, confirmed=False, message="contact not found")
            existing = _CONTACTS.get(cid_lookup) or {}
            existing.update(payload.get("fields", {}))
            _CONTACTS.put(cid_lookup, existing)
            return ToolResult(ok=True, confirmed=True, data=existing, external_id=cid_lookup)
        if operation == "contact.get":
            cid_raw = payload.get("id")
            cid_lookup = cid_raw if isinstance(cid_raw, str) else None
            c = _CONTACTS.get(cid_lookup) if cid_lookup else None
            if not c:
                return ToolResult(ok=False, confirmed=False, message="contact not found")
            return ToolResult(ok=True, confirmed=True, data=c, external_id=cid_lookup)
        if operation == "contact.list":
            ws = payload.get("workspace_id", principal.workspace_id)
            items = [c for c in _CONTACTS.all() if c.get("workspace_id") == ws]
            return ToolResult(ok=True, confirmed=True, data={"contacts": items, "count": len(items)})
        if operation == "company.upsert":
            key = (payload.get("name") or "").lower() or str(uuid.uuid4())
            existing = _COMPANIES.get(key) or {
                "id": str(uuid.uuid4()),
                "workspace_id": principal.workspace_id,
            }
            existing.update(payload)
            existing["workspace_id"] = existing.get("workspace_id", principal.workspace_id)
            _COMPANIES.put(key, existing)
            return ToolResult(ok=True, confirmed=True, data=existing,
                              external_id=existing["id"],
                              message="persisted to crm.companies.json")
        if operation == "deal.create":
            did = str(uuid.uuid4())
            rec = {
                "id": did,
                "workspace_id": principal.workspace_id,
                "stage": "new",
                **payload,
            }
            _DEALS.put(did, rec)
            return ToolResult(ok=True, confirmed=True, data=rec, external_id=did)
        if operation == "deal.update_stage":
            did_raw = payload.get("id")
            did_lookup = did_raw if isinstance(did_raw, str) else None
            d = _DEALS.get(did_lookup) if did_lookup else None
            if not d:
                return ToolResult(ok=False, confirmed=False, message="deal not found")
            d["stage"] = payload.get("stage", d.get("stage"))
            _DEALS.put(did, d)
            return ToolResult(ok=True, confirmed=True, data=d, external_id=did)
        if operation == "deal.list":
            ws = payload.get("workspace_id", principal.workspace_id)
            items = [d for d in _DEALS.all() if d.get("workspace_id") == ws]
            return ToolResult(ok=True, confirmed=True, data={"deals": items, "count": len(items)})
        if operation == "activity.record":
            aid = str(uuid.uuid4())
            rec = {
                "id": aid,
                "workspace_id": principal.workspace_id,
                **payload,
            }
            _ACTIVITIES.put(aid, rec)
            return ToolResult(ok=True, confirmed=True, data=rec, external_id=aid)
        return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")


register(CRMConnector())
