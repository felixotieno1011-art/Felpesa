from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All app config, loaded once from env / .env at import."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- app ----
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "Felpesa"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ---- db ----
    postgres_user: str
    postgres_password: str
    postgres_db: str
    # When running inside docker compose, host is "db"; on host machine it's "localhost".
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ---- redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- auth ----
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    # ---- rate limiting / fraud ----
    rate_limit_transfers_per_min: int = 5
    rate_limit_auth_per_min: int = 10
    require_pin: bool = True
    payment_provider: str = "daraja"
    withdrawal_mode: str = "simulated"  # simulated | provider
    fraud_amount_threshold: int = 50_000
    fraud_rapid_window_seconds: int = 60
    fraud_rapid_max_transfers: int = 3

    # ---- daraja (sandbox only) ----
    mpesa_env: str = "sandbox"
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = "174379"
    mpesa_passkey: str = ""
    mpesa_callback_base_url: str = ""
    mpesa_callback_secret: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
