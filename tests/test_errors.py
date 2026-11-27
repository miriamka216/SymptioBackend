
from pathlib import Path
import re
import runpy

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
import pytest

from shared.errors import (
    REQUEST_ID_HEADER,
    ApiError,
    ErrorCode,
    ErrorResponse,
    install_error_handlers,
)

ROOT = Path(__file__).resolve().parents[1]
API_MD = ROOT / "Zadanie 1 - Modely, FineTuning, Používanie" / "API.md"


class Parameters(BaseModel):
    epochs: int = Field(gt=0)


class JobRequest(BaseModel):
    model_id: str
    parameters: Parameters


def build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/files/{file_id}")
    def get_file(file_id: str):
        raise ApiError(
            ErrorCode.FILE_NOT_FOUND,
            "Súbor neexistuje alebo k nemu nie je prístup.",
            details={"file_id": file_id},
        )

    @app.get("/items")
    def list_items(limit: int = Query(20, ge=1, le=100)):
        return {"limit": limit}

    @app.post("/jobs")
    def create_job(job: JobRequest):
        return job

    @app.get("/boom")
    def boom():
        raise RuntimeError("postgresql://admin:private-password@db")

    return app


@pytest.fixture
def client():
    with TestClient(build_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def test_every_error_code_from_api_md_has_matching_status():
    documented = set(re.findall(r"`(\d{3}) ([A-Z_]+)`", API_MD.read_text(encoding="utf-8")))
    assert len(documented) >= 48
    for status, code in documented:
        assert ErrorCode(code).http_status == int(status), code


def test_extra_codes_have_expected_statuses():
    assert ErrorCode.VALIDATION_ERROR.http_status == 422
    assert ErrorCode.UNAUTHENTICATED.http_status == 401
    assert ErrorCode.FORBIDDEN.http_status == 403
    assert ErrorCode.INTERNAL_ERROR.http_status == 500
    assert ErrorCode.FILE_NOT_FOUND == "FILE_NOT_FOUND"


def test_api_error_uses_common_format_and_incoming_request_id(client):
    response = client.get("/files/file_image_01", headers={REQUEST_ID_HEADER: "req_demo_12"})

    assert response.status_code == 404
    assert response.headers[REQUEST_ID_HEADER] == "req_demo_12"
    assert response.json() == {
        "error": {
            "code": "FILE_NOT_FOUND",
            "message": "Súbor neexistuje alebo k nemu nie je prístup.",
            "details": {"file_id": "file_image_01"},
            "request_id": "req_demo_12",
            "retryable": False,
        }
    }
    ErrorResponse.model_validate(response.json())


def test_request_id_is_generated_when_header_missing(client):
    response = client.get("/files/x")
    request_id = response.json()["error"]["request_id"]

    assert re.fullmatch(r"req_[0-9a-f]{32}", request_id)
    assert response.headers[REQUEST_ID_HEADER] == request_id


@pytest.mark.parametrize("bad_id", ["", "a" * 129, "req 01", "req_01á"])
def test_invalid_incoming_request_id_is_replaced(client, bad_id):
    response = client.get("/files/x", headers={REQUEST_ID_HEADER: bad_id.encode()})
    assert response.json()["error"]["request_id"].startswith("req_")
    assert response.json()["error"]["request_id"] != bad_id


def test_query_error_returns_invalid_query(client):
    response = client.get("/items", params={"limit": 0})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_QUERY"
    assert error["details"]["fields"][0]["field"] == "limit"
    assert error["retryable"] is False


def test_body_error_returns_validation_error_with_fields(client):
    response = client.post("/jobs", json={"model_id": "mdl_train_base", "parameters": {"epochs": -1}})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Požiadavka obsahuje neplatnú hodnotu."
    assert [f["field"] for f in error["details"]["fields"]] == ["parameters.epochs"]
    assert error["details"]["fields"][0]["reason"]


def test_malformed_json_returns_validation_error(client):
    response = client.post("/jobs", content=b"{not json", headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"][0]["field"] == "body"


def test_unexpected_error_returns_500_without_internal_details(client):
    response = client.get("/boom", headers={REQUEST_ID_HEADER: "req_boom"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Nastala neočakávaná chyba servera.",
            "details": {},
            "request_id": "req_boom",
            "retryable": False,
        }
    }
    assert "private-password" not in response.text
    assert "RuntimeError" not in response.text


def test_file_service_has_error_handlers_and_infra_endpoints():
    app = runpy.run_path(str(ROOT / "services" / "file-service" / "main.py"))["app"]
    assert ApiError in app.exception_handlers

    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"service": "file-service", "status": "ok"}
        assert "/readyz" in client.get("/openapi.json").json()["paths"]
