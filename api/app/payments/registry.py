from app.core.config import get_settings
from app.payments.adapters.daraja_adapter import DarajaProvider
from app.payments.interfaces import PaymentProvider


class UnknownProvider(Exception):
    pass


_PROVIDERS: dict[str, type[PaymentProvider]] = {"daraja": DarajaProvider}


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().payment_provider
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise UnknownProvider(name)
    return cls()
