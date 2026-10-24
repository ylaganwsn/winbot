from fastapi.testclient import TestClient

from winbot.api import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_path_is_404():
    assert client.get("/nope").status_code == 404