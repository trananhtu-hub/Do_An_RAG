from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.auth import AuthUser
from app.main import app

client = TestClient(app)
USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _as(email: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=USER_ID, email=email)


def _anonymous() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_admin_tu_choi_nguoi_dung_thuong(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "quantri@example.com")
    _as("hocvien@example.com")
    try:
        response = client.get("/admin/stats")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "admin_required"
    finally:
        _anonymous()


def test_admin_cho_phep_email_trong_danh_sach(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "quantri@example.com, khac@example.com")
    _as("QUANTRI@example.com")
    try:
        response = client.get("/me")
        assert response.status_code == 200
        assert response.json()["is_admin"] is True
    finally:
        _anonymous()


def test_me_mac_dinh_khong_phai_admin(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "")
    _as("hocvien@example.com")
    try:
        response = client.get("/me")
        assert response.status_code == 200
        assert response.json()["is_admin"] is False
    finally:
        _anonymous()


def test_cac_tuyen_du_lieu_can_dang_nhap() -> None:
    for path in ("/me", "/meta", "/documents", "/quiz/domains", "/quiz/attempts"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["detail"]["code"] == "missing_token", path
