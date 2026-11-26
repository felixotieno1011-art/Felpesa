"""Inbox messages. These only db.add(); the caller's commit makes them atomic with the money."""
from decimal import Decimal

from app.models import Notification


def _ksh(x: Decimal) -> str:
    return f"Ksh{x:,.2f}"


def add(db, user_id, kind, title, body, txn_id) -> None:
    db.add(Notification(user_id=user_id, kind=kind, title=title[:80], body=body[:300],
                        transaction_id=txn_id))


def after_transfer(db, *, txn, from_w, to_w, from_after, to_after) -> None:
    amt = _ksh(txn.amount)
    if not from_w.is_system:
        if txn.type == "transfer":
            add(db, from_w.user_id, "sent", "Money sent",
                f"{amt} sent. New balance {_ksh(from_after)}.", txn.id)
        else:
            titles = {"paybill": "Bill paid", "buygoods": "Payment made", "airtime": "Airtime bought"}
            add(db, from_w.user_id, "payment", titles.get(txn.type, "Payment"),
                f"{amt} paid: {txn.description or txn.type}. New balance {_ksh(from_after)}.", txn.id)
    if txn.type == "transfer" and not to_w.is_system:
        add(db, to_w.user_id, "received", "Money received",
            f"You received {amt}. New balance {_ksh(to_after)}.", txn.id)


def after_cash(db, *, txn, user_id, balance_after) -> None:
    amt = _ksh(txn.amount)
    if txn.type == "deposit":
        add(db, user_id, "deposit", "Deposit received",
            f"{amt} added to your wallet. New balance {_ksh(balance_after)}.", txn.id)
    else:
        add(db, user_id, "withdrawal", "Withdrawal",
            f"{amt} withdrawn. New balance {_ksh(balance_after)}.", txn.id)
