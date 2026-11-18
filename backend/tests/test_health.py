import json
import logging

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import app

client = TestClient(app)


def test_health_tra_ve_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_json_formatter_tao_log_mot_dong() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Xin chào",
        args=(),
        exc_info=None,
    )
    data = json.loads(JsonFormatter().format(record))
    assert data["level"] == "INFO"
    assert data["message"] == "Xin chào"
    assert "timestamp" in data


def test_model_mac_dinh_la_gemini_3_8_flash(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL_DEFAULT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.gemini_model_default == "gemini-3.8-flash"
