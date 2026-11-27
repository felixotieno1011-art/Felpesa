"""Scheduler: lock prevents overlap, round runs the reconciliation, loop survives errors."""
import asyncio

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services import recon_scheduler


async def _clear():
    await get_redis_client().delete(recon_scheduler.LOCK_KEY)


async def test_run_once_takes_lock_and_second_caller_skips(monkeypatch):
    await _clear()
    calls = []

    async def fake(db, min_age_seconds=300):
        calls.append(1)
        return {"checked": 0, "outcomes": {}, "withdrawals_without_payout": []}

    monkeypatch.setattr(recon_scheduler, "run_reconciliation", fake)
    assert await recon_scheduler.run_once() is not None
    assert await recon_scheduler.run_once() is None  # lock still held
    assert len(calls) == 1
    await _clear()


async def test_loop_survives_a_failing_round(monkeypatch):
    await _clear()
    monkeypatch.setattr(get_settings(), "recon_interval_seconds", 1)
    n = []

    async def boom():
        n.append(1)
        raise RuntimeError("provider down")

    monkeypatch.setattr(recon_scheduler, "run_once", boom)
    monkeypatch.setattr(asyncio, "sleep", _fast_sleep())
    task = asyncio.create_task(recon_scheduler.loop())
    for _ in range(50):
        await _real_sleep(0.01)
        if len(n) >= 3:
            break
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert len(n) >= 3  # kept going after the first error


_real_sleep = asyncio.sleep


def _fast_sleep():
    async def s(_t):
        await _real_sleep(0)
    return s
