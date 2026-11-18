from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Cấu hình đọc từ biến môi trường, ưu tiên tệp .env ở thư mục gốc repo."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model_default: str = "gemini-3.8-flash"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""

    @property
    def has_gemini_api_key(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_supabase_config(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


def get_settings() -> Settings:
    return Settings()
