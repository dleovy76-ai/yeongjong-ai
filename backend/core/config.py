import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the project root regardless of the process's cwd, so
# `uvicorn main:app` from backend/ and `pytest` from the repo root both
# find the same .env file.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://yeongjong:yeongjong@localhost:5432/yeongjong_ai"
    database_test_url: str = "postgresql+psycopg://yeongjong:yeongjong@localhost:5432/yeongjong_ai_test"

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-real-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    frontend_origin: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
