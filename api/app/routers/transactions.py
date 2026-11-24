import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.deps import CurrentUser, SessionDep
from app.schemas.common import PageMeta
from app.schemas.transaction import (
    TransactionFilter,
    TransactionListResponse,
    TransactionOut,
)
from app.services import message_service, transaction_service, wallet_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_my_transactions(
    user: CurrentUser,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    direction: Annotated[str | None, Query()] = None,
    flagged_fraud: Annotated[bool | None, Query()] = None,
) -> TransactionListResponse:
    try:
        filters = TransactionFilter(
            type=type, status=status, direction=direction, flagged_fraud=flagged_fraud  # type: ignore[arg-type]
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    items, total = await transaction_service.list_transactions(
        db, user_id=user.id, filters=filters, limit=limit, offset=offset
    )
    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    msgs = await message_service.build_messages(db, list(items), wallet.id if wallet else None)
    outs = []
    for t in items:
        o = TransactionOut.model_validate(t)
        o.message = msgs.get(t.id)
        outs.append(o)
    return TransactionListResponse(
        items=outs,
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: uuid.UUID,
    user: CurrentUser,
    db: SessionDep,
) -> TransactionOut:
    txn = await transaction_service.get_transaction(
        db, transaction_id=transaction_id, user_id=user.id
    )
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    msgs = await message_service.build_messages(db, [txn], wallet.id if wallet else None)
    out = TransactionOut.model_validate(txn)
    out.message = msgs.get(txn.id)
    return out
