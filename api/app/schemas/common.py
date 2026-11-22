from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class RegisterResponse(BaseModel):
    id: str
    phone: str
    full_name: str
    wallet_id: str


class PageMeta(BaseModel):
    """Standard pagination metadata for any list endpoint."""
    total: int
    limit: int
    offset: int


class Paginated(BaseModel, Generic[T]):
    """Standard paginated envelope. Client reads `items` + `meta`."""
    items: list[T]
    meta: PageMeta
