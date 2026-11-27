"""Background loop: re-check stuck payments on a timer. One runner at a time via a Redis lock."""
import asyncio
import logging

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.services.payment_recon_service import run_reconciliation

log = logging.getLogger(__name__)
LOCK_KEY = "lock:payment-reconciliation"


async def run_once() -> dict | None:
    """Take the lock, run one reconciliation round. None = another worker holds the lock."""
    interval = get_settings().recon_interval_seconds
    redis = get_redis_client()
    got = await redis.set(LOCK_KEY, "1", nx=True, ex=max(30, interval))
    if not got:
        return None
    async with SessionLocal() as db:
        return await run_reconciliation(db)


async def loop() -> None:
    interval = get_settings().recon_interval_seconds
    await asyncio.sleep(min(interval, 30))  # let the app finish starting
    while True:
        try:
            out = await run_once()
            if out and (out["checked"] or out["withdrawals_without_payout"]):
                log.info("reconciliation: %s", out)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("reconciliation round failed")
        await asyncio.sleep(interval)
