import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.deps import CurrentUser, SessionDep
from app.schemas.common import PageMeta
from app.schemas.transaction import (
    TransactionFilter,
    TransactionListResponse,
    TransactionOut,
)
from app.services import transaction_service

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
    filters = TransactionFilter(
        type=type, status=status, direction=direction, flagged_fraud=flagged_fraud  # type: ignore[arg-type]
    )
    items, total = await transaction_service.list_transactions(
        db, user_id=user.id, filters=filters, limit=limit, offset=offset
    )
    return TransactionListResponse(
        items=[TransactionOut.model_validate(t) for t in items],
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
    return TransactionOut.model_validate(txn)
