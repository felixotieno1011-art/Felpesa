from pydantic import BaseModel


class RegisterResponse(BaseModel):
    id: str
    phone: str
    full_name: str
    wallet_id: str
