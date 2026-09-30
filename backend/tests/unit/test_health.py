"""健康检查契约测试。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_live_probe() -> None:
    response = TestClient(create_app()).get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_probe_without_external_dependencies() -> None:
    response = TestClient(create_app()).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
