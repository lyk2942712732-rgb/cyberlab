from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://cyberlab:cyberlab@postgres/cyberlab"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = Field(min_length=32)
    orchestrator_secret: str = Field(min_length=32)
    orchestrator_url: str = "ws://orchestrator:8081"
    public_origin: str = "http://localhost:8080"
    token_minutes: int = Field(default=480, ge=5, le=1440)
    upload_dir: str = "/var/lib/cyberlab/uploads/target-images"
    max_upload_mb: int = Field(default=1024, ge=1, le=1024)
    max_active_sessions: int = Field(default=20, ge=1, le=100)
    kali_image: str = "cyberlab/kali:local"
    kali_cpu: float = Field(default=2, ge=0.25, le=8)
    kali_memory_mb: int = Field(default=2048, ge=512, le=8192)
    activity_dir: str = "/var/lib/cyberlab/activity"
    # Path resolved by Docker for Kali bind mounts; rootless deployments may
    # expose a different host path than the orchestrator container sees.
    activity_host_dir: str = "/var/lib/cyberlab/activity"
    activity_max_mb: int = Field(default=64, ge=1, le=1024)
    worker_interval: float = Field(default=1, ge=1, le=30)
    health_timeout: int = Field(default=90, ge=5, le=180)
    testing: bool = False


@lru_cache
def settings() -> Settings:
    return Settings()
