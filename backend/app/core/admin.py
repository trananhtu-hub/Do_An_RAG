from __future__ import annotations

from .auth import AuthUser
from .config import get_settings


def is_admin(user: AuthUser) -> bool:
    """Quyền quản trị lấy từ danh sách ADMIN_EMAILS, không đổi RLS."""
    email = (user.email or "").strip().lower()
    return bool(email) and email in get_settings().admin_email_set
