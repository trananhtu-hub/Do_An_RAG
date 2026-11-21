from __future__ import annotations

import os

from .config import PROJECT_ROOT

_ENV_KEYS = (
    "GEMINI_API_KEY",
    "GEMINI_MODEL_DEFAULT",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
)


def load_environment() -> dict[str, str]:
    """Đọc .env ở thư mục gốc; biến môi trường thật được ưu tiên hơn."""
    values: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    for key in _ENV_KEYS:
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values
