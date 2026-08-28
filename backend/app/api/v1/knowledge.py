"""Knowledge base and audit log routes."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.models.orm import AuditLog, Document
from app.rag.service import add_document
from app.schemas import AuditOut, DocumentCreate, DocumentOut

router = APIRouter(tags=["knowledge"])


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    name: str = Form(...),
    mime_type: str = Form("text/plain"),
    access_roles: str = Form(""),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DocumentOut:
    roles = [r.strip() for r in access_roles.split(",") if r.strip()]
    if file is not None:
        raw = await file.read()
        if not mime_type or mime_type == "text/plain":
            mime_type = file.content_type or "text/plain"
        doc = add_document(
            db,
            company_id=p.workspace_id,
            name=name,
            mime_type=mime_type,
            access_roles=roles,
            content_base64=base64.b64encode(raw).decode("ascii"),
        )
    else:
        if text is None:
            raise HTTPException(status_code=400, detail="either file or text is required")
        doc = add_document(
            db,
            company_id=p.workspace_id,
            name=name,
            mime_type=mime_type,
            access_roles=roles,
            text=text,
        )
    db.commit()
    return DocumentOut(
        id=doc.id,
        name=doc.name,
        mime_type=doc.mime_type,
        access_roles=doc.access_roles or [],
        indexed=doc.indexed,
    )


@router.post("/documents/json", response_model=DocumentOut)
def upload_document_json(
    payload: DocumentCreate,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """JSON variant for programmatic uploads (kept for SDK / tests)."""
    doc = add_document(
        db,
        company_id=p.workspace_id,
        name=payload.name,
        mime_type=payload.mime_type,
        access_roles=payload.access_roles,
        text=payload.text,
        content_base64=payload.content_base64,
    )
    db.commit()
    return DocumentOut(
        id=doc.id,
        name=doc.name,
        mime_type=doc.mime_type,
        access_roles=doc.access_roles or [],
        indexed=doc.indexed,
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    rows = db.query(Document).filter(Document.company_id == p.workspace_id).all()
    return [
        DocumentOut(
            id=d.id,
            name=d.name,
            mime_type=d.mime_type,
            access_roles=d.access_roles or [],
            indexed=d.indexed,
        )
        for d in rows
    ]


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[AuditOut]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.company_id == p.workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditOut(
            id=a.id,
            actor=a.actor,
            action=a.action,
            target_type=a.target_type,
            target_id=a.target_id,
            details=a.details or {},
            created_at=a.created_at,
        )
        for a in rows
    ]

