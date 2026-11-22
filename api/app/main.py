from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.routers import auth, ledger, reconciliation, transactions, transfers, wallets

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(wallets.router)
app.include_router(transfers.router)
app.include_router(transactions.router)
app.include_router(ledger.router)
app.include_router(reconciliation.router)


@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
