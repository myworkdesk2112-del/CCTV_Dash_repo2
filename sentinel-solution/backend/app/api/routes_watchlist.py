from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..watchlist.service import watchlist_service
from .auth import Principal, require_role
from .deps import get_db

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistCreate(BaseModel):
    plate: str
    reason: str


@router.get("")
def list_watchlist(db: Session = Depends(get_db), _principal: Principal = Depends(require_role("investigator"))):
    from ..db.models import WatchlistEntry

    return [
        {"plate": e.plate, "reason": e.reason, "added_at": e.added_at.isoformat()}
        for e in db.query(WatchlistEntry).order_by(WatchlistEntry.added_at.desc()).limit(5000).all()
    ]


@router.post("")
def add_watchlist_entry(
    entry: WatchlistCreate,
    db: Session = Depends(get_db),
    _admin: Principal = Depends(require_role("admin")),
):
    watchlist_service.add(db, entry.plate, entry.reason)
    return {"status": "added", "plate": entry.plate}
