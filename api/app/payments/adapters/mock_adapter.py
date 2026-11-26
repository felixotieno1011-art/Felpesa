"""Test-only provider. Refused in production by the registry."""
import uuid

from app.payments.interfaces import (
    CollectionRequest, CollectionResult, PaymentProvider, PayoutRequest,
)


class MockProvider(PaymentProvider):
    name = "mock"
    payout_behavior = "accept"  # accept | reject | timeout
    payout_status = "pending"  # what query_payout reports: paid | failed | pending
    payout_status = "pending"  # what query_payout reports: paid | failed | pending

    async def initiate_collection(self, req: CollectionRequest) -> CollectionResult:
        return CollectionResult(True, provider_ref="mock-" + uuid.uuid4().hex[:12])

    async def query_status(self, provider_ref: str) -> str:
        return "paid"

    async def initiate_payout(self, req: PayoutRequest) -> CollectionResult:
        b = MockProvider.payout_behavior
        if b == "timeout":
            raise TimeoutError("mock timeout")
        if b == "reject":
            return CollectionResult(False, message="mock rejected")
        return CollectionResult(True, provider_ref="mockpay-" + uuid.uuid4().hex[:10])

    async def query_payout(self, reference: str) -> str:
        return MockProvider.payout_status

    async def query_payout(self, reference: str) -> str:
        return MockProvider.payout_status
