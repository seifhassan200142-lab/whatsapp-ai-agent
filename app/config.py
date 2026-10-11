import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    groq_whisper_model: str = "whisper-large-v3-turbo"
    meta_access_token: SecretStr = SecretStr("")
    meta_app_secret: SecretStr = SecretStr("")
    meta_verify_token: SecretStr = SecretStr("")
    meta_phone_number_id: str = ""
    meta_graph_version: str = Field(default="v26.0", pattern=r"^v\d+\.0$")
    admin_api_key: SecretStr = SecretStr("")
    db_path: Path = ROOT / "data/conversations.sqlite3"
    knowledge_path: Path = ROOT / "data/knowledge.md"
    history_messages: int = Field(default=10, ge=2, le=20)
    max_audio_bytes: int = Field(default=16_000_000, ge=1024, le=25_000_000)
    groq_min_interval_seconds: float = Field(default=3, ge=0, le=60)
    groq_max_calls_per_day: int = Field(default=100, ge=1, le=10000)
    request_timeout: float = Field(default=35, ge=1, le=120)
    worker_enabled: bool = True

    def missing(self) -> list[str]:
        fields = ("groq_api_key", "meta_access_token", "meta_app_secret",
                  "meta_verify_token", "meta_phone_number_id", "admin_api_key")
        return [name.upper() for name in fields if not secret(getattr(self, name))]


def secret(value: SecretStr | str) -> str:
    text = value.get_secret_value() if isinstance(value, SecretStr) else value
    return text.strip()


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")
    values = {}
    for name in Settings.model_fields:
        raw = os.environ.get(name.upper())
        if raw is not None:
            raw = raw.strip()
            values[name] = "" if raw.startswith("PASTE_") else raw
    for name in ("db_path", "knowledge_path"):
        if name in values:
            path = Path(values[name])
            values[name] = path if path.is_absolute() else ROOT / path
    settings = Settings(**values)
    for name in ("admin_api_key", "meta_verify_token"):
        if secret(getattr(settings, name)) and len(secret(getattr(settings, name))) < 32:
            raise ValueError(f"{name.upper()} must contain at least 32 characters. Run python -m scripts.prepare_env")
    if settings.meta_phone_number_id and not settings.meta_phone_number_id.isdigit():
        raise ValueError("META_PHONE_NUMBER_ID must contain digits only (the ID, not the phone number).")
    return settings
