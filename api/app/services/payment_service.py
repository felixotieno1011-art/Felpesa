import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Merchant, Transaction
from app.services import transfer_service


class MerchantNotFound(Exception):
    pass


async def pay_merchant(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    from_wallet_id: uuid.UUID,
    kind: str,
    number: str,
    account_ref: str | None,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
) -> Transaction:
    merchant = await db.scalar(
        select(Merchant).where(
            Merchant.kind == kind,
            Merchant.number == number,
            Merchant.is_active.is_(True),
        )
    )
    if merchant is None:
        raise MerchantNotFound(f"{kind} {number}")

    desc = f"{kind} {number} - {merchant.name}"
    if account_ref:
        desc += f" acc {account_ref}"

    return await transfer_service.execute_transfer(
        db,
        initiated_by=user_id,
        from_wallet_id=from_wallet_id,
        to_wallet_id=merchant.wallet_id,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        description=desc,
        txn_type=kind,
    )
