from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.models import Wallet
from app.schemas.wallet import WalletOut

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("/me", response_model=WalletOut)
async def get_my_wallet(user: CurrentUser, db: SessionDep) -> WalletOut:
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return WalletOut.model_validate(wallet)
