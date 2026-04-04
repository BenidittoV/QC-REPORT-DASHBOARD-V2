from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "QC Dashboard API"
    secret_key: str = "change-this-in-production"
    session_max_age_seconds: int = 60 * 60 * 12

    database_url: str = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    cors_origins: str = "*"

    storage_root: str = str(BASE_DIR / "storage")
    admin_storage_subdir: str = "admin"
    manual_storage_subdir: str = "manual"

    keep_uploaded_files: bool = False

    sql_echo: bool = False
    db_pool_size: int = 3
    db_max_overflow: int = 2
    db_pool_timeout_seconds: int = 30

    ingest_chunk_size: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()