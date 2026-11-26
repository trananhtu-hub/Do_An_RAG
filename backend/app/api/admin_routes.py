from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import api_error, get_current_user
from app.core.admin import is_admin
from app.core.auth import AuthUser
from app.models.admin_schemas import AdminDailyPoint, AdminStatsResponse, AdminTotals
from app.services.admin_stats import AdminStatsNotConfigured, AdminStatsService

router = APIRouter(tags=["admin"])


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not is_admin(user):
        raise api_error(403, "admin_required", "Bạn không có quyền truy cập trang quản trị.")
    return user


def get_admin_stats_service() -> AdminStatsService:
    return AdminStatsService()


@router.get(
    "/admin/stats",
    response_model=AdminStatsResponse,
    summary="Thống kê vận hành (chỉ quản trị viên)",
)
def admin_stats(
    days: int = Query(default=30, ge=1, le=365),
    user: AuthUser = Depends(require_admin),
    service: AdminStatsService = Depends(get_admin_stats_service),
) -> AdminStatsResponse:
    try:
        data = service.stats(days)
    except AdminStatsNotConfigured as exc:
        raise api_error(503, "admin_stats_unavailable", str(exc)) from None
    return AdminStatsResponse(
        period_days=data["period_days"],
        totals=AdminTotals(**data["totals"]),
        daily=[AdminDailyPoint(**point) for point in data["daily"]],
        generated_at=data["generated_at"],
    )
