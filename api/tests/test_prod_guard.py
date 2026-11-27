"""APP_ENV=prod refuses unsafe settings."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings

OK = dict(_env_file=None, app_env="prod", postgres_user="u", postgres_db="d",
          postgres_password="a-long-random-db-password", jwt_secret="x" * 40,
          require_pin=True, withdrawal_mode="provider", payment_provider="daraja")


def test_safe_prod_config_loads():
    assert Settings(**OK).app_env == "prod"


@pytest.mark.parametrize("bad", [
    {"postgres_password": "felpesa_dev"},
    {"require_pin": False},
    {"withdrawal_mode": "simulated"},
    {"payment_provider": "mock"},
])
def test_unsafe_prod_config_is_refused(bad):
    with pytest.raises(ValidationError):
        Settings(**{**OK, **bad})
