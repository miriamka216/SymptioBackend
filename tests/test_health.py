from pathlib import Path
import runpy

import pytest
from fastapi.testclient import TestClient

from shared.health import create_app

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("gateway", "model-service", "file-service", "training-service", "provider-service", "chat-service", "runtime-service")


@pytest.mark.parametrize("service", SERVICES)
def test_service_liveness(service):
    app = runpy.run_path(str(ROOT / "services" / service / "main.py"))["app"]
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"service": service, "status": "ok"}
        assert client.get("/openapi.json").status_code == 200
        assert "/readyz" in client.get("/openapi.json").json()["paths"]


def test_readiness_success():
    with TestClient(create_app("test", {"db": lambda: True})) as client:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"service": "test", "status": "ready", "checks": {"db": "ok"}}


def test_readiness_false_probe():
    with TestClient(create_app("test", {"db": lambda: False})) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["checks"] == {"db": "unavailable"}


def test_readiness_exception_does_not_disclose_secret():
    def fail():
        raise RuntimeError("private-password")

    with TestClient(create_app("test", {"broker": fail})) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
        assert "private-password" not in response.text
        assert client.get("/healthz").status_code == 200
