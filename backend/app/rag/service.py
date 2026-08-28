"""Company knowledge base + RAG (PRD §22)."""
from __future__ import annotations

import base64
from pathlib import Path

from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.config import get_settings
from app.models.orm import Document
from app.rag.index import get_index


def _storage_dir(workspace_id: str) -> Path:
    s = get_settings()
    base = Path(s.document_storage_dir)
    p = base / workspace_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_text(*, mime_type: str, text: str | None, raw: bytes | None) -> str:
    if text is not None:
        return text
    if raw is None:
        return ""
    if mime_type == "application/pdf":
        try:
            from io import BytesIO

            from PyPDF2 import PdfReader

            reader = PdfReader(BytesIO(raw))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:  # noqa: BLE001
            return ""
    if mime_type.endswith("wordprocessingml.document"):
        try:
            from io import BytesIO

            from docx import Document as Docx

            d = Docx(BytesIO(raw))
            return "\n".join(p.text for p in d.paragraphs)
        except Exception:  # noqa: BLE001
            return ""
    return raw.decode("utf-8", errors="ignore")


def add_document(
    db: Session,
    *,
    company_id: str,
    name: str,
    mime_type: str,
    access_roles: list[str],
    text: str | None = None,
    content_base64: str | None = None,
) -> Document:
    doc = Document(
        company_id=company_id,
        name=name,
        source="upload",
        mime_type=mime_type,
        access_roles=access_roles,
        storage_path="",
        indexed=False,
    )
    db.add(doc)
    db.flush()

    raw: bytes | None = None
    if content_base64:
        raw = base64.b64decode(content_base64)
    body = _extract_text(mime_type=mime_type, text=text, raw=raw)
    if body:
        path = _storage_dir(company_id) / f"{doc.id}.txt"
        path.write_text(body, encoding="utf-8")
        doc.storage_path = str(path)
        get_index().add(
            workspace_id=company_id,
            document_id=doc.id,
            document_name=name,
            text=body,
            access_roles=access_roles,
        )
        doc.indexed = True
    record(
        db,
        company_id=company_id,
        actor="user",
        action="document.indexed",
        target_type="document",
        target_id=doc.id,
        details={"name": name, "mime_type": mime_type},
    )
    db.flush()
    return doc


