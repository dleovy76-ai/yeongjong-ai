import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the project root regardless of the process's cwd, so
# `uvicorn main:app` from backend/ and `pytest` from the repo root both
# find the same .env file.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")


def _with_psycopg_driver(url: str) -> str:
    """Railway's managed Postgres injects DATABASE_URL as plain postgresql://
    (or postgres://) - SQLAlchemy needs the +psycopg driver marker to use
    psycopg3 (the only Postgres driver this project depends on; psycopg2
    isn't installed), or it fails at connection time with a confusing
    "no module named psycopg2" error. Rewritten here once, at the boundary,
    rather than requiring every deploy env to know this."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://yeongjong:yeongjong@localhost:5432/yeongjong_ai"
    database_test_url: str = "postgresql+psycopg://yeongjong:yeongjong@localhost:5432/yeongjong_ai_test"

    @field_validator("database_url", "database_test_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return _with_psycopg_driver(v)

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-real-env-use-at-least-32-random-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # Optional, operator-supplied cost estimate (USD per 1K tokens) - left at 0
    # (meaning "not configured") rather than a hard-coded guess, since pricing
    # varies by model/tier and a wrong guess would misrepresent real spend.
    gemini_input_cost_per_1k_tokens: float = 0.0
    gemini_output_cost_per_1k_tokens: float = 0.0
    anthropic_api_key: str = ""

    data_go_kr_api_key: str = ""
    nts_biz_verify_api_key: str = ""

    naver_client_id: str = ""
    naver_client_secret: str = ""

    frontend_origin: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


_DEFAULT_JWT_SECRET = "change-me-in-real-env-use-at-least-32-random-bytes"

settings = Settings()

if settings.is_production and settings.jwt_secret == _DEFAULT_JWT_SECRET:
    raise RuntimeError(
        "ENVIRONMENT=production인데 JWT_SECRET이 기본값 그대로입니다. "
        "실제 배포 전에 무작위 값(32바이트 이상)으로 반드시 바꾸세요."
    )
