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

    # Gemini chỉ dùng cho embedding 768 chiều.
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""
    # Danh sách email quản trị, phân tách bằng dấu phẩy; rỗng nghĩa là không ai.
    admin_emails: str = ""

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(
            email.strip().lower() for email in self.admin_emails.split(",") if email.strip()
        )

    @property
    def has_gemini_api_key(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_deepseek_api_key(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def has_supabase_config(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


def get_settings() -> Settings:
    return Settings()
