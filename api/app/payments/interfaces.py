"""Provider-independent payment interface. The ledger never talks to a provider directly."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CollectionRequest:
    phone: str          # international format, with or without +
    amount: Decimal
    reference: str
    description: str
    callback_url: str


@dataclass
class CollectionResult:
    accepted: bool
    provider_ref: str | None = None   # e.g. Daraja CheckoutRequestID
    secondary_ref: str | None = None  # e.g. Daraja MerchantRequestID
    message: str | None = None


@dataclass
class PayoutRequest:
    phone: str
    amount: Decimal
    reference: str


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def initiate_collection(self, req: CollectionRequest) -> CollectionResult: ...

    @abstractmethod
    async def query_status(self, provider_ref: str) -> str:
        """Return 'paid', 'failed' or 'pending'. Raise on network errors."""

    async def initiate_payout(self, req: PayoutRequest) -> CollectionResult:
        raise NotImplementedError(f"{self.name} has no payout support yet")

    async def query_payout(self, reference: str) -> str:
        """Return 'paid', 'failed' or 'pending' for a payout we sent with this reference."""
        raise NotImplementedError(f"{self.name} has no payout lookup yet")

    async def query_payout(self, reference: str) -> str:
        """Return 'paid', 'failed' or 'pending' for a payout we sent with this reference."""
        raise NotImplementedError(f"{self.name} has no payout lookup yet")
