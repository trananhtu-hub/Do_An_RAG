import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.logging import configure_logging
from app.services.generation.providers import LLMError
from app.services.sessions.types import SessionNotFound, SessionStoreError

ALLOWED_ORIGINS = ["http://localhost:3000"]

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Chatbot RAG luyện thi AWS SAA-C03", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(SessionNotFound, _session_not_found)
    app.add_exception_handler(SessionStoreError, _session_store_error)
    app.add_exception_handler(LLMError, _llm_error)
    app.include_router(router)
    logger.info("Khởi tạo ứng dụng FastAPI")
    return app


async def _session_not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": {"code": "session_not_found", "message": str(exc)}},
    )


async def _session_store_error(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("Lỗi kho phiên: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": "session_store_unavailable",
                "message": "Không truy cập được kho phiên hội thoại, thử lại sau.",
            }
        },
    )


async def _llm_error(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("Lỗi nhà cung cấp LLM: %s", exc)
    return JSONResponse(
        status_code=502,
        content={
            "detail": {
                "code": "generation_failed",
                "message": "Dịch vụ sinh câu trả lời tạm thời không khả dụng.",
            }
        },
    )


app = create_app()
