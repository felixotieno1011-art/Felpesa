"""Transaction read operations. Write (transfer) lives in transfer_service."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, Wallet
from app.schemas.transaction import TransactionFilter


async def list_transactions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    filters: TransactionFilter | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    """Return (items, total) for the user's transactions.

    A transaction is "the user's" if they initiated it, or if either wallet
    is one of their wallets. This captures both sent and received money.
    """
    filters = filters or TransactionFilter()

    # The user's wallets — needed for the in/out join.
    wallet_ids = list(
        (await db.scalars(select(Wallet.id).where(Wallet.user_id == user_id))).all()
    )

    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))

    # Ownership: initiated by this user, OR from/to one of their wallets.
    if wallet_ids:
        ownership = or_(
            Transaction.initiated_by == user_id,
            Transaction.from_wallet_id.in_(wallet_ids),
            Transaction.to_wallet_id.in_(wallet_ids),
        )
    else:
        ownership = Transaction.initiated_by == user_id
    stmt = stmt.where(ownership)
    count_stmt = count_stmt.where(ownership)

    # Direction filter (in = received, out = sent)
    if filters.direction == "in" and wallet_ids:
        stmt = stmt.where(Transaction.to_wallet_id.in_(wallet_ids))
        count_stmt = count_stmt.where(Transaction.to_wallet_id.in_(wallet_ids))
    elif filters.direction == "out" and wallet_ids:
        stmt = stmt.where(Transaction.from_wallet_id.in_(wallet_ids))
        count_stmt = count_stmt.where(Transaction.from_wallet_id.in_(wallet_ids))

    # Scalar filters
    if filters.type:
        stmt = stmt.where(Transaction.type == filters.type)
        count_stmt = count_stmt.where(Transaction.type == filters.type)
    if filters.status:
        stmt = stmt.where(Transaction.status == filters.status)
        count_stmt = count_stmt.where(Transaction.status == filters.status)
    if filters.flagged_fraud is not None:
        stmt = stmt.where(Transaction.flagged_fraud == filters.flagged_fraud)
        count_stmt = count_stmt.where(Transaction.flagged_fraud == filters.flagged_fraud)

    # Order + paginate
    stmt = stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
    items = list((await db.scalars(stmt)).all())
    total = int((await db.scalar(count_stmt)) or 0)
    return items, total


async def get_transaction(
    db: AsyncSession, *, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction | None:
    """Fetch a transaction if the user owns either side of it."""
    wallet_ids = list(
        (await db.scalars(select(Wallet.id).where(Wallet.user_id == user_id))).all()
    )
    ownership = or_(
        Transaction.initiated_by == user_id,
        *(
            [Transaction.from_wallet_id.in_(wallet_ids), Transaction.to_wallet_id.in_(wallet_ids)]
            if wallet_ids
            else []
        ),
    )
    return await db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, ownership)
    )
