"""The suite must never run against the dev database."""
from app.core.config import get_settings


def test_suite_uses_test_database_and_redis_db():
    s = get_settings()
    assert s.postgres_db == "felpesa_test"
    assert s.redis_url.endswith("/15")
