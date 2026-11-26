import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, update

from app.deps import CurrentUser, SessionDep
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: Notification) -> dict:
    return {
        "id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body,
        "transaction_id": str(n.transaction_id) if n.transaction_id else None,
        "is_read": n.is_read, "created_at": n.created_at.isoformat(),
    }


def _mine(user_id):
    return (Notification.user_id == user_id, Notification.deleted_at.is_(None))


@router.get("")
async def list_notifications(
    user: CurrentUser, db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    rows = (await db.scalars(
        select(Notification).where(*_mine(user.id))
        .order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )).all()
    unread = await db.scalar(
        select(func.count()).select_from(Notification)
        .where(*_mine(user.id), Notification.is_read.is_(False))
    )
    return {"items": [_out(n) for n in rows], "unread": unread or 0}


@router.get("/unread-count")
async def unread_count(user: CurrentUser, db: SessionDep) -> dict:
    n = await db.scalar(
        select(func.count()).select_from(Notification)
        .where(*_mine(user.id), Notification.is_read.is_(False))
    )
    return {"unread": n or 0}


@router.post("/read-all")
async def read_all(user: CurrentUser, db: SessionDep) -> dict:
    await db.execute(update(Notification).where(*_mine(user.id)).values(is_read=True))
    await db.commit()
    return {"ok": True}


async def _get_mine(db, user, nid: uuid.UUID) -> Notification:
    n = await db.scalar(select(Notification).where(Notification.id == nid, *_mine(user.id)))
    if n is None:
        raise HTTPException(404, "Not found")
    return n


@router.post("/{nid}/read")
async def mark_read(nid: uuid.UUID, user: CurrentUser, db: SessionDep) -> dict:
    n = await _get_mine(db, user, nid)
    n.is_read = True
    await db.commit()
    return {"ok": True}


@router.delete("/{nid}")
async def delete_notification(nid: uuid.UUID, user: CurrentUser, db: SessionDep) -> dict:
    """Soft delete: hides the message only. The transaction and ledger are untouched."""
    n = await _get_mine(db, user, nid)
    n.deleted_at = func.now()
    n.is_read = True
    await db.commit()
    return {"ok": True}
