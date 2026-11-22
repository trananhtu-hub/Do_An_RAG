"""Chạy backend với chuỗi provider chỉ định cho các phép đo Giai đoạn 4.

DeepSeek là nhà cung cấp duy nhất cho sinh văn bản; Gemini chỉ còn embedding.
Không sửa config mặc định; chỉ ghi đè trong tiến trình này.

Chạy:
    PYTHONUTF8=1 python scripts/phase4_serve.py --provider deepseek_primary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn  # noqa: E402
from app.api.deps import get_session_repository  # noqa: E402
from app.main import app  # noqa: E402
from app.services.chat import ChatService, set_chat_service  # noqa: E402
from app.services.conversation import load_conversation_config  # noqa: E402
from app.services.generation import (  # noqa: E402
    GenerationService,
    PromptLibrary,
    build_provider_chain,
    load_generation_config,
)
from app.services.generation.logger import QueryLogWriter  # noqa: E402
from app.services.generation.settings import load_environment  # noqa: E402
from app.services.retrieval import build_default_service as build_retrieval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backend Giai đoạn 4 với provider chỉ định")
    parser.add_argument("--provider", default="deepseek_primary")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    env = load_environment()
    gen_config = load_generation_config().with_overrides({"chain": [args.provider]})
    chain = build_provider_chain(gen_config, environ=env)
    writer = QueryLogWriter(
        env.get("DATABASE_URL"),
        enabled=gen_config.logging.enabled,
        table=gen_config.logging.table,
    )
    generation = GenerationService(
        gen_config,
        chain,
        retrieval=build_retrieval(),
        prompts=PromptLibrary(gen_config.prompt_root),
        log_writer=writer,
    )
    set_chat_service(ChatService(get_session_repository(), generation, load_conversation_config()))
    print(f"Provider chain: {', '.join(chain.names)}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
