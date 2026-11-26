from app.payments.interfaces import CollectionRequest, CollectionResult, PaymentProvider
from app.services import daraja  # called as daraja.<fn> so tests can monkeypatch it


class DarajaProvider(PaymentProvider):
    name = "daraja"

    async def initiate_collection(self, req: CollectionRequest) -> CollectionResult:
        resp = await daraja.stk_push(
            phone=req.phone.lstrip("+"),
            amount=int(req.amount),
            reference=req.reference,
            description=req.description,
            callback_url=req.callback_url,
        )
        ok = str(resp.get("ResponseCode")) == "0" and bool(resp.get("CheckoutRequestID"))
        return CollectionResult(
            accepted=ok,
            provider_ref=resp.get("CheckoutRequestID"),
            secondary_ref=resp.get("MerchantRequestID"),
            message=resp.get("ResponseDescription"),
        )

    async def query_status(self, provider_ref: str) -> str:
        q = await daraja.stk_query(provider_ref)
        code = q.get("ResultCode")
        if code is None:
            return "pending"  # no result yet, or an error body
        return "paid" if str(code) == "0" else "failed"
