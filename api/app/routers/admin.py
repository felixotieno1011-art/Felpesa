from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import AdminUser, SessionDep
from app.services.payment_recon_service import run_reconciliation

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reconcile-payments")
async def reconcile_payments(
    admin: AdminUser, db: SessionDep,
    min_age_seconds: Annotated[int, Query(ge=0, le=86400)] = 300,
) -> dict:
    """Re-check stuck payment attempts against the provider. Safe to run repeatedly."""
    return await run_reconciliation(db, min_age_seconds=min_age_seconds)
