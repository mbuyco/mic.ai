from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret_file(path: str | None, fallback: str) -> str:
    if not path:
        return fallback
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"Secret file at {path} is empty")
    return value


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "sqlite+pysqlite:///./micai.db"
    redis_url: str = "redis://localhost:6379/0"

    admin_api_key: str = "dev-admin-key"
    admin_api_key_file: str | None = None

    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_verify_token_file: str | None = None
    whatsapp_access_token: str = "dev-access-token"
    whatsapp_access_token_file: str | None = None
    whatsapp_phone_number_id: str = "dev-phone-id"
    whatsapp_phone_number_id_file: str | None = None

    outbound_reply_enabled: bool = False
    require_invoke_prefix: bool = True
    invoke_prefixes: str = "michael:,@michael,/ask"
    freeform_window_hours: int = 24

    queue_poll_timeout_seconds: int = 2
    queue_max_attempts: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MICAI_")

    def model_post_init(self, __context: object) -> None:
        self.admin_api_key = _read_secret_file(self.admin_api_key_file, self.admin_api_key)
        self.whatsapp_verify_token = _read_secret_file(
            self.whatsapp_verify_token_file, self.whatsapp_verify_token
        )
        self.whatsapp_access_token = _read_secret_file(
            self.whatsapp_access_token_file, self.whatsapp_access_token
        )
        self.whatsapp_phone_number_id = _read_secret_file(
            self.whatsapp_phone_number_id_file, self.whatsapp_phone_number_id
        )


settings = Settings()
