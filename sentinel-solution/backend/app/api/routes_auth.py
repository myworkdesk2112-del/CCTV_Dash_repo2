from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import ApiKeyEntry
from .auth import Principal, hash_key, require_role
from .deps import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class ApiKeyCreate(BaseModel):
    user_id: str
    role: str  # "admin" | "investigator" | "viewer"
    department: str | None = None


@router.post("/api-keys")
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    _admin: Principal = Depends(require_role("admin")),
):
    if body.role not in ("admin", "investigator", "viewer"):
        raise HTTPException(400, "role must be one of admin, investigator, viewer")
    # A non-admin key with no department is unrestricted (see
    # auth.department_scope), so leaving the field blank used to mint a
    # statewide-access key by default (security review 2026-09-26).
    # Unscoped access now has to be an explicit admin grant, not an omission.
    department = (body.department or "").strip() or None
    if body.role != "admin" and department is None:
        raise HTTPException(400, "department is required for viewer and investigator keys")
    body.department = department
    raw_key = secrets.token_urlsafe(24)
    db.add(ApiKeyEntry(key_hash=hash_key(raw_key), user_id=body.user_id, role=body.role, department=body.department))
    db.commit()
    # The raw key is only ever returned here, at creation time — the DB only
    # ever stores its hash, so this is the one and only time it's visible.
    return {"api_key": raw_key, "user_id": body.user_id, "role": body.role}


@router.get("/api-keys")
def list_api_keys(db: Session = Depends(get_db), _admin: Principal = Depends(require_role("admin"))):
    return [
        {"user_id": e.user_id, "role": e.role, "department": e.department, "created_at": e.created_at.isoformat()}
        for e in db.query(ApiKeyEntry).all()
    ]


@router.get("/whoami")
def whoami(principal: Principal = Depends(require_role("viewer"))):
    return {"user_id": principal.user_id, "role": principal.role, "department": principal.department}
