from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from shared.auth import DEV_TOKENS_ENV, Identity, require_identity
from shared.errors import install_error_handlers
from shared.events import EventEnvelope
from shared.idempotency import (
    IDEMPOTENCY_KEY_HEADER,
    optional_idempotency_key,
    require_idempotency_key,
)
from shared.pagination import Page, PaginationParams, pagination_params
from shared.responses import AcceptedResponse

DEV_TOKENS = "token-one:usr_demo_01,token-two:usr_demo_02"


def build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/me")
    def me(identity: Identity = Depends(require_identity)):
        return identity

    @app.post("/jobs")
    def start_job(key: str = Depends(require_idempotency_key)):
        return {"key": key}

    @app.post("/optional")
    def optional(key: str | None = Depends(optional_idempotency_key)):
        return {"key": key}

    @app.get("/items")
    def items(page: PaginationParams = Depends(pagination_params)):
        return page

    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(DEV_TOKENS_ENV, DEV_TOKENS)
    with TestClient(build_app()) as test_client:
        yield test_client


# --- auth ---

@pytest.mark.parametrize("token, user_id", [("token-one", "usr_demo_01"), ("token-two", "usr_demo_02")])
def test_known_tokens_map_to_their_users(client, token, user_id):
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": user_id}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer unknown"}, {"Authorization": "Basic token-one"}])
def test_missing_or_unknown_token_returns_401(client, headers):
    response = client.get("/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


# --- idempotency ---

def test_valid_idempotency_key_is_returned(client):
    response = client.post("/jobs", headers={IDEMPOTENCY_KEY_HEADER: "key-01"})
    assert response.json() == {"key": "key-01"}


@pytest.mark.parametrize(
    "headers, reason",
    [
        ({}, "Hlavička chýba."),
        ({IDEMPOTENCY_KEY_HEADER: "   "}, "Hodnota je prázdna."),
        ({IDEMPOTENCY_KEY_HEADER: "k" * 256}, "Hodnota je príliš dlhá (max. 255 znakov)."),
    ],
)
def test_invalid_idempotency_key_returns_validation_error(client, headers, reason):
    response = client.post("/jobs", headers=headers)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"] == [{"field": "Idempotency-Key", "reason": reason}]


def test_optional_idempotency_key_may_be_missing(client):
    assert client.post("/optional").json() == {"key": None}


# --- pagination ---

def test_pagination_defaults(client):
    assert client.get("/items").json() == {"cursor": None, "limit": 20}


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_out_of_range_returns_invalid_query(client, limit):
    response = client.get("/items", params={"limit": limit})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_page_serializes_items_and_next_cursor():
    assert Page[int](items=[1, 2]).model_dump() == {"items": [1, 2], "next_cursor": None}


# --- responses ---

def test_accepted_response_is_extended_with_service_id():
    class DownloadAccepted(AcceptedResponse):
        download_id: str

    body = DownloadAccepted(download_id="dl_01", status="queued", status_url="/api/v1/model-downloads/dl_01")
    assert body.model_dump() == {
        "status": "queued",
        "status_url": "/api/v1/model-downloads/dl_01",
        "download_id": "dl_01",
    }


# --- events ---

def test_event_envelope_defaults_and_utc():
    event = EventEnvelope(type="model.download.requested", data={"download_id": "dl_01"})
    dumped = event.model_dump(mode="json")
    assert dumped["occurred_at"].endswith("Z")
    assert dumped["data"] == {"download_id": "dl_01"}
    assert event.message_id != EventEnvelope(type="training.requested").message_id


def test_event_time_is_converted_to_utc():
    local = datetime(2026, 11, 17, 20, 0, tzinfo=timezone(timedelta(hours=2)))
    event = EventEnvelope(type="training.requested", occurred_at=local)
    assert event.occurred_at == datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
    assert event.occurred_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "training.requested", "occurred_at": datetime(2026, 11, 17, 18, 0)},
        {"type": "TrainingRequested"},
    ],
)
def test_event_rejects_naive_time_and_bad_type(kwargs):
    with pytest.raises(ValidationError):
        EventEnvelope(**kwargs)
