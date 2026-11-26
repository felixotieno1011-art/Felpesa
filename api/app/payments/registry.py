from app.core.config import get_settings
from app.payments.adapters.daraja_adapter import DarajaProvider
from app.payments.adapters.mock_adapter import MockProvider
from app.payments.interfaces import PaymentProvider


class UnknownProvider(Exception):
    pass


_PROVIDERS: dict[str, type[PaymentProvider]] = {"daraja": DarajaProvider, "mock": MockProvider}


def get_provider(name: str | None = None) -> PaymentProvider:
    s = get_settings()
    name = name or s.payment_provider
    if name == "mock" and s.app_env == "prod":
        raise UnknownProvider("mock provider is not allowed in production")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise UnknownProvider(name)
    return cls()
