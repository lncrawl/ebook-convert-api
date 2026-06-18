from __future__ import annotations

import math
import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _cgroup_cpu_count() -> int:
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            return max(1, math.floor(int(quota) / int(period)))
    except Exception:
        pass
    return os.cpu_count() or 1


def _cgroup_memory_limit_mb() -> int:
    try:
        val = open("/sys/fs/cgroup/memory.max").read().strip()
        if val != "max":
            return int(val) // (1024 * 1024)
    except Exception:
        pass
    try:
        return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) // (1024 * 1024)
    except Exception:
        return 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    memory_per_job_mb: int = Field(default=256, gt=0)
    conversion_timeout_seconds: int = Field(default=300, gt=0)
    max_upload_mb: int = Field(default=100, gt=0)
    use_auth: bool = False
    max_concurrent_jobs: int = Field(default=0, ge=0)  # 0 = auto-size from cgroups

    @model_validator(mode="after")
    def resolve_concurrency(self) -> "Settings":
        if self.max_concurrent_jobs == 0:
            cpu_limit = _cgroup_cpu_count()
            mem_limit = max(1, _cgroup_memory_limit_mb() // self.memory_per_job_mb)
            object.__setattr__(self, "max_concurrent_jobs", max(1, min(cpu_limit, mem_limit)))
        return self


settings = Settings()
