"""Fraud detection hooks. v1: two rules, no blocking.

Design principle: FLAG, don't block. False positives in a wallet
service are worse than false negatives — blocking a legitimate rent
payment is catastrophic, flagging it for admin review is cheap.
Same for velocity: the 4th transfer in a minute is likely legitimate
(a user paying bills), but worth a look.

Blocking is v2, and should only come after you've measured false
positive rate on real traffic.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Transaction

settings = get_settings()


@dataclass
class FlagResult:
    flagged: bool
    reason: str | None = None  # short machine-readable code, e.g. "amount_above_threshold"


async def evaluate(
    db: AsyncSession,
    *,
    user_id,
    amount: Decimal,
) -> FlagResult:
    """Run all fraud rules. Return the first reason that fires.

    Order matters: high-value single transaction is more actionable
    than velocity, so check it first.
    """
    # Rule 1: amount threshold
    if amount > Decimal(settings.fraud_amount_threshold):
        return FlagResult(
            flagged=True,
            reason=f"amount_above_threshold:{amount}",
        )

    # Rule 2: velocity — count user's transfers in the last window
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.fraud_rapid_window_seconds)
    recent = int(
        (await db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.initiated_by == user_id,
                Transaction.type == "transfer",
                Transaction.created_at >= cutoff,
            )
        )) or 0
    )
    if recent >= settings.fraud_rapid_max_transfers:
        return FlagResult(
            flagged=True,
            reason=f"velocity:{recent + 1}_in_{settings.fraud_rapid_window_seconds}s",
        )

    return FlagResult(flagged=False)
