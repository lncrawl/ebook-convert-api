from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    conversion_timeout_seconds: int = Field(default=300, gt=0)
    max_upload_mb: int = Field(default=100, gt=0)
    use_auth: bool = False
    max_concurrent_jobs: int = Field(default=2, gt=0)


settings = Settings()
