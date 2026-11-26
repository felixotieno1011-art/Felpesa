"""Reject reuse of an Idempotency-Key with different request parameters."""


class IdempotencyConflict(Exception):
    pass


def ensure_same(txn, **expected) -> None:
    for field, want in expected.items():
        have = getattr(txn, field)
        if field == "description":
            have = have or None
            want = want or None
        if have != want:
            raise IdempotencyConflict(field)
