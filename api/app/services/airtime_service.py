import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Merchant, Transaction
from app.services import transfer_service


class ProviderNotFound(Exception):
    pass


async def buy_airtime(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    from_wallet_id: uuid.UUID,
    phone: str,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
) -> Transaction:
    provider = await db.scalar(
        select(Merchant)
        .where(Merchant.kind == "airtime", Merchant.is_active.is_(True))
        .order_by(Merchant.created_at.desc())
        .limit(1)
    )
    if provider is None:
        raise ProviderNotFound("airtime provider")

    return await transfer_service.execute_transfer(
        db,
        initiated_by=user_id,
        from_wallet_id=from_wallet_id,
        to_wallet_id=provider.wallet_id,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        description=f"airtime {phone}",
        txn_type="airtime",
    )
