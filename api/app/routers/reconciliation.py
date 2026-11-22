from fastapi import APIRouter

from app.deps import AdminUser, SessionDep
from app.schemas.reconciliation import ReconciliationReport
from app.services import reconciliation_service

router = APIRouter(tags=["reconciliation"])


@router.get("/reconciliation", response_model=ReconciliationReport)
async def reconcile(
    admin: AdminUser, db: SessionDep
) -> ReconciliationReport:
    """Admin-only: prove every transaction balances and every wallet
    cache matches its ledger. The finance flex endpoint."""
    return await reconciliation_service.full_reconciliation(db)
