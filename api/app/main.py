from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.idempotency import IdempotencyConflict
from app.core.db import engine
from app.core.redis import close_redis, get_redis_client
from app.routers import notifications, auth, audit, deposits, airtime, ledger, mpesa, payments, pin, reconciliation, transactions, transfers, wallets

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB reachable
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    # Verify Redis reachable (ping)
    redis_client = get_redis_client()
    await redis_client.ping()
    yield
    # Shutdown: clean up
    await close_redis()
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

@app.exception_handler(IdempotencyConflict)
async def _idempotency_conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Idempotency-Key was already used with different parameters"},
    )


app.include_router(auth.router)
app.include_router(notifications.router)
app.include_router(wallets.router)
app.include_router(transfers.router)
app.include_router(deposits.router)
app.include_router(transactions.router)
app.include_router(ledger.router)
app.include_router(reconciliation.router)
app.include_router(audit.router)
app.include_router(payments.router)
app.include_router(pin.router)
app.include_router(airtime.router)
app.include_router(mpesa.router)
app.include_router(mpesa.hook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    redis_client = get_redis_client()
    await redis_client.ping()
    return {"status": "ok", "db": "ok", "redis": "ok"}
