from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw"
DEFAULT_VERSION = "v1"
PIPELINE_VERSION = "1.0.0"
DEFAULT_STATS_PATH = PROJECT_ROOT / "data" / "processed" / "ingestion_stats.json"
DEFAULT_EMBED_CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "embed_cache.json"
DEFAULT_ANALYSIS_PATH = PROJECT_ROOT / "docs" / "ingestion-analysis.md"
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
EXPECTED_QUESTIONS = 390

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
EMBEDDING_BATCH_SIZE = 50
EMBEDDING_TASK_TYPE = "RETRIEVAL_DOCUMENT"
# Hạn mức free tier của gemini-embedding-001 là 30.000 token/phút; giữ biên an toàn.
# Ước lượng token cho embedding bám sát thực đo (~2,3 ký tự/token với tiếng Việt).
EMBEDDING_TPM_LIMIT = 28_000
EMBEDDING_MAX_TOKENS_PER_REQUEST = 20_000
EMBEDDING_CHARS_PER_TOKEN = 2.3
EMBEDDING_MAX_INPUT_TOKENS = 2048

PARENT_MIN_TOKENS = 800
PARENT_MAX_TOKENS = 1200
CHILD_MIN_TOKENS = 300
CHILD_MAX_TOKENS = 500
CHILD_OVERLAP_RATIO = 0.12
CHARS_PER_TOKEN = 3.0


def load_env(path: Path | None = None) -> dict[str, str]:
    """Đọc tệp .env đơn giản, không ghi log giá trị."""
    env_path = path or PROJECT_ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = field(repr=False)
    database_url: str = field(repr=False)
    embedding_model: str = EMBEDDING_MODEL
    embedding_dim: int = EMBEDDING_DIM
    embedding_batch_size: int = EMBEDDING_BATCH_SIZE

    @property
    def gemini_api_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        for part in self.gemini_api_key.split(","):
            key = part.strip()
            if key and key not in keys:
                keys.append(key)
        return tuple(keys)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        values = env if env is not None else load_env()
        api_key = values.get("GEMINI_API_KEY", "").strip()
        database_url = values.get("DATABASE_URL", "").strip()
        if not api_key:
            raise RuntimeError("Thiếu GEMINI_API_KEY trong .env")
        if not database_url:
            raise RuntimeError("Thiếu DATABASE_URL trong .env")
        return cls(gemini_api_key=api_key, database_url=database_url)
