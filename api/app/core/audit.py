"""Audit log writer. Non-committal: caller controls the transaction.

The audit() helper only db.add()'s the AuditLog — it does NOT commit.
That's deliberate: the audit record must be part of the same transaction
as the action it records. If the action rolls back, the audit row rolls
back too. This is the property that makes the audit trail trustworthy:
it can never say "transfer completed" if the transfer was rolled back.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Add an AuditLog row to the current session. Caller commits.

    `metadata` is stored as JSONB. Use it for action-specific details
    (e.g. {"amount": "100.0000", "to_wallet": "..."} for a transfer).
    Do NOT put secrets here — this table is readable by admins.
    """
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
