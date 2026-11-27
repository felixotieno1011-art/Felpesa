"""M-Pesa-style confirmation messages, built from transactions + ledger."""
import uuid
from datetime import timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerEntry, Transaction


NAIROBI = timezone(timedelta(hours=3))  # Kenya: UTC+3, no daylight saving


def _ksh(x: Decimal) -> str:
    return f"Ksh{x:,.2f}"


def _text(t: Transaction, wallet_id: uuid.UUID, bal: Decimal | None) -> str:
    code = t.id.hex[:10].upper()
    amt = _ksh(t.amount)
    created = t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)
    when = created.astimezone(NAIROBI).strftime("%d/%m/%y at %I:%M %p")
    tail = f" New balance {_ksh(bal)}." if bal is not None else ""

    if t.type in ("paybill", "buygoods"):
        target = (t.description or "").split(" ", 1)[-1]
        body = f"{amt} paid to {target}"
    elif t.type == "airtime":
        target = (t.description or "").split(" ", 1)[-1]
        body = f"{amt} airtime bought for {target}"
    elif t.type == "withdrawal_reversal":
        body = f"{amt} returned to your wallet (withdrawal failed)"
    elif t.type == "deposit":
        body = f"{amt} deposited to your wallet"
    elif t.type == "withdrawal":
        if getattr(t, "status", None) == "pending":
            body = f"{amt} withdrawal is being processed"
        else:
            body = f"{amt} withdrawn from your wallet"
    elif t.from_wallet_id == wallet_id:
        body = f"{amt} sent to wallet ...{str(t.to_wallet_id)[-6:]}"
    else:
        body = f"{amt} received from wallet ...{str(t.from_wallet_id)[-6:]}"
    return f"{code} Confirmed. {body} on {when}.{tail}"


async def build_messages(
    db: AsyncSession, txns: list[Transaction], wallet_id: uuid.UUID | None
) -> dict[uuid.UUID, str]:
    if wallet_id is None or not txns:
        return {}
    rows = await db.execute(
        select(LedgerEntry.transaction_id, LedgerEntry.balance_after).where(
            LedgerEntry.transaction_id.in_([t.id for t in txns]),
            LedgerEntry.wallet_id == wallet_id,
        )
    )
    balances = {tid: b for tid, b in rows.all()}
    return {t.id: _text(t, wallet_id, balances.get(t.id)) for t in txns}
