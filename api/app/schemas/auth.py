import re

from pydantic import BaseModel, Field, field_validator

# E.164-ish: + then 10–15 digits. Kenya numbers are +254 + 9 digits.
PHONE_RE = re.compile(r"^\+[1-9]\d{9,14}$")


class RegisterRequest(BaseModel):
    phone: str = Field(..., description="E.164 format, e.g. +254712345678")
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("phone must be E.164 format, e.g. +254712345678")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name must not be blank")
        return v


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
