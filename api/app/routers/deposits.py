from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.deps import CurrentUser, SessionDep
from app.pin_dep import require_pin
from app.schemas.transaction import TransactionOut
from app.services import deposit_service, wallet_service, withdrawal_service

router = APIRouter(tags=["deposits"])


def simulated_deposits_only() -> None:
    """Self-service deposits create money. Never expose them in production."""
    if get_settings().app_env == "prod":
        raise HTTPException(404, "Not found")


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=19, decimal_places=4, description="Amount in KES")
    currency: str = Field(..., min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=500)


class WithdrawalRequest(DepositRequest):
    pass


@router.post("/deposits", response_model=TransactionOut, status_code=201,
             dependencies=[Depends(simulated_deposits_only)])
async def create_deposit(
    payload: DepositRequest,
    user: CurrentUser,
    db: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> TransactionOut:
    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if wallet is None:
        raise HTTPException(404, "Wallet not found")
    from decimal import Decimal
    try:
        txn = await deposit_service.deposit(
            db,
            user_id=user.id,
            to_wallet_id=wallet.id,
            amount=Decimal(str(payload.amount)),
            currency=payload.currency.upper(),
            idempotency_key=idempotency_key,
            description=payload.description,
        )
    except deposit_service.DailyLimitExceeded as e:
        raise HTTPException(429, str(e))
    except deposit_service.DepositError as e:
        raise HTTPException(422, str(e))
    return TransactionOut.model_validate(txn)


@router.post("/withdrawals", response_model=TransactionOut, status_code=201,
             dependencies=[Depends(simulated_deposits_only), Depends(require_pin)])
async def create_withdrawal(
    payload: WithdrawalRequest,
    user: CurrentUser,
    db: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> TransactionOut:
    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if wallet is None:
        raise HTTPException(404, "Wallet not found")
    if get_settings().withdrawal_mode == "provider":
        try:
            txn = await withdrawal_service.request_withdrawal(
                db, user=user, wallet=wallet, amount=payload.amount,
                currency=payload.currency.upper(), idempotency_key=idempotency_key,
                description=payload.description,
            )
        except deposit_service.DepositError as e:  # also covers InsufficientFunds
            raise HTTPException(422, str(e))
        except deposit_service.WithdrawalError as e:
            raise HTTPException(422, str(e))
        return TransactionOut.model_validate(txn)
    from decimal import Decimal
    try:
        txn = await deposit_service.withdraw(
            db,
            user_id=user.id,
            from_wallet_id=wallet.id,
            amount=Decimal(str(payload.amount)),
            currency=payload.currency.upper(),
            idempotency_key=idempotency_key,
            description=payload.description,
        )
    except deposit_service.InsufficientFunds as e:
        raise HTTPException(422, str(e))
    except deposit_service.DepositError as e:
        raise HTTPException(422, str(e))
    return TransactionOut.model_validate(txn)
