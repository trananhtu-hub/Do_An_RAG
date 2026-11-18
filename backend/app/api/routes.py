from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Kiểm tra tình trạng backend")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
