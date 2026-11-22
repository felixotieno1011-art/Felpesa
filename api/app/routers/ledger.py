import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.deps import CurrentUser, SessionDep
from app.models import LedgerEntry, Wallet
from app.schemas.common import PageMeta
from app.schemas.ledger import LedgerEntryOut, LedgerListResponse

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/{wallet_id}", response_model=LedgerListResponse)
async def get_wallet_ledger(
    wallet_id: uuid.UUID,
    user: CurrentUser,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LedgerListResponse:
    # Access control: wallet owner OR admin. Reject everyone else with 403.
    wallet = await db.get(Wallet, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    if wallet.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this ledger")

    items = list(
        (
            await db.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.wallet_id == wallet_id)
                .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    total = int(
        (await db.scalar(
            select(func.count(LedgerEntry.id)).where(LedgerEntry.wallet_id == wallet_id)
        )) or 0
    )

    return LedgerListResponse(
        items=[LedgerEntryOut.model_validate(e) for e in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )
