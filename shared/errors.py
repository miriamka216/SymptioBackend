"""Spoločný formát chyby podľa API.md (Zadanie 1, časť „Spoločný formát chyby“)."""
import logging
import re
import uuid
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}")


class ErrorCode(StrEnum):
    """Chybový kód API; každý člen nesie aj HTTP stav, s ktorým sa vracia."""

    http_status: HTTPStatus

    def __new__(cls, code: str, http_status: int) -> "ErrorCode":
        member = str.__new__(cls, code)
        member._value_ = code
        member.http_status = HTTPStatus(http_status)
        return member

    # Spoločné kódy
    VALIDATION_ERROR = ("VALIDATION_ERROR", 422)
    INVALID_QUERY = ("INVALID_QUERY", 422)
    UNAUTHENTICATED = ("UNAUTHENTICATED", 401)
    FORBIDDEN = ("FORBIDDEN", 403)
    IDEMPOTENCY_CONFLICT = ("IDEMPOTENCY_CONFLICT", 409)
    INTERNAL_ERROR = ("INTERNAL_ERROR", 500)

    # 404 – zdroj neexistuje alebo nie je viditeľný
    DEVICE_NOT_FOUND = ("DEVICE_NOT_FOUND", 404)
    CATALOG_MODEL_NOT_FOUND = ("CATALOG_MODEL_NOT_FOUND", 404)
    MODEL_VARIANT_NOT_FOUND = ("MODEL_VARIANT_NOT_FOUND", 404)
    DOWNLOAD_NOT_FOUND = ("DOWNLOAD_NOT_FOUND", 404)
    MODEL_NOT_FOUND = ("MODEL_NOT_FOUND", 404)
    FILE_NOT_FOUND = ("FILE_NOT_FOUND", 404)
    MODEL_OR_FILE_NOT_FOUND = ("MODEL_OR_FILE_NOT_FOUND", 404)
    TRAINING_JOB_NOT_FOUND = ("TRAINING_JOB_NOT_FOUND", 404)
    CONNECTION_NOT_FOUND = ("CONNECTION_NOT_FOUND", 404)
    MODEL_OR_AGENT_NOT_FOUND = ("MODEL_OR_AGENT_NOT_FOUND", 404)
    CONVERSATION_NOT_FOUND = ("CONVERSATION_NOT_FOUND", 404)
    MODEL_CONVERSATION_OR_AGENT_NOT_FOUND = ("MODEL_CONVERSATION_OR_AGENT_NOT_FOUND", 404)
    GENERATION_NOT_FOUND = ("GENERATION_NOT_FOUND", 404)

    # 409 – konflikt so stavom zdroja
    MODEL_IN_USE = ("MODEL_IN_USE", 409)
    TRAINING_ALREADY_STARTED = ("TRAINING_ALREADY_STARTED", 409)
    TRAINING_NOT_DRAFT = ("TRAINING_NOT_DRAFT", 409)
    TRAINING_ALREADY_COMPLETED = ("TRAINING_ALREADY_COMPLETED", 409)
    RESULT_NOT_READY = ("RESULT_NOT_READY", 409)
    CONNECTION_IN_USE = ("CONNECTION_IN_USE", 409)
    CONVERSATION_BUSY = ("CONVERSATION_BUSY", 409)
    CONVERSATION_MODEL_MISMATCH = ("CONVERSATION_MODEL_MISMATCH", 409)
    GENERATION_NOT_WAITING_FOR_TOOLS = ("GENERATION_NOT_WAITING_FOR_TOOLS", 409)
    TOOL_RESULT_CONFLICT = ("TOOL_RESULT_CONFLICT", 409)

    # 413 a 415 – upload súborov
    FILE_TOO_LARGE = ("FILE_TOO_LARGE", 413)
    UNSUPPORTED_MEDIA_TYPE = ("UNSUPPORTED_MEDIA_TYPE", 415)

    # 422 – doménovo neplatná požiadavka
    MODEL_INCOMPATIBLE = ("MODEL_INCOMPATIBLE", 422)
    PERFORMANCE_NOT_VERIFIED = ("PERFORMANCE_NOT_VERIFIED", 422)
    MODEL_NOT_LOCAL = ("MODEL_NOT_LOCAL", 422)
    INVALID_FILE = ("INVALID_FILE", 422)
    TRAINING_CONFIGURATION_INVALID = ("TRAINING_CONFIGURATION_INVALID", 422)
    TRAINING_DATA_INVALID = ("TRAINING_DATA_INVALID", 422)
    INVALID_TRAINING_PARAMETER = ("INVALID_TRAINING_PARAMETER", 422)
    PROVIDER_NOT_SUPPORTED = ("PROVIDER_NOT_SUPPORTED", 422)
    INVALID_CREDENTIAL_FORMAT = ("INVALID_CREDENTIAL_FORMAT", 422)
    INVALID_CONNECTION_SETTINGS = ("INVALID_CONNECTION_SETTINGS", 422)
    CONNECTION_NOT_VALID = ("CONNECTION_NOT_VALID", 422)
    MODEL_PRICING_UNAVAILABLE = ("MODEL_PRICING_UNAVAILABLE", 422)
    MODEL_NOT_READY = ("MODEL_NOT_READY", 422)
    CONTEXT_LIMIT_EXCEEDED = ("CONTEXT_LIMIT_EXCEEDED", 422)
    UNSUPPORTED_INPUT_OR_PARAMETER = ("UNSUPPORTED_INPUT_OR_PARAMETER", 422)
    TOOL_RESULT_INVALID = ("TOOL_RESULT_INVALID", 422)

    # 5xx – závislosti a zdroje
    PROVIDER_ERROR = ("PROVIDER_ERROR", 502)
    DEVICE_UNAVAILABLE = ("DEVICE_UNAVAILABLE", 503)
    MODEL_SOURCE_UNAVAILABLE = ("MODEL_SOURCE_UNAVAILABLE", 503)
    CONNECTOR_UNAVAILABLE = ("CONNECTOR_UNAVAILABLE", 503)
    INSUFFICIENT_STORAGE = ("INSUFFICIENT_STORAGE", 507)


class FieldError(BaseModel):
    field: str
    reason: str


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Vyhodená doménová chyba; handler ju prevedie na ErrorResponse."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.headers = headers or {}


def get_request_id(request: Request) -> str:
    cached = getattr(request.state, "request_id", None)
    if cached:
        return cached
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    if _REQUEST_ID_PATTERN.fullmatch(incoming):
        request_id = incoming
    else:
        request_id = f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    return request_id


def error_response(
    request: Request,
    code: ErrorCode,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or {},
            request_id=request_id,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=code.http_status,
        content=body.model_dump(mode="json"),
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )


def _field_path(error: dict[str, Any]) -> str:
    location = error["loc"]
    if error["type"] == "json_invalid":
        return location[0]
    return ".".join(str(part) for part in location[1:]) or str(location[0])


async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        request,
        exc.code,
        exc.message,
        details=exc.details,
        retryable=exc.retryable,
        headers=exc.headers,
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    fields = [
        FieldError(field=_field_path(error), reason=error["msg"]).model_dump()
        for error in errors
    ]
    if errors and all(error["loc"][0] == "query" for error in errors):
        return error_response(
            request,
            ErrorCode.INVALID_QUERY,
            "Parametre query obsahujú neplatnú hodnotu.",
            details={"fields": fields},
        )
    return error_response(
        request,
        ErrorCode.VALIDATION_ERROR,
        "Požiadavka obsahuje neplatnú hodnotu.",
        details={"fields": fields},
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.error("Neočakávaná chyba, request_id=%s", request_id, exc_info=exc)
    return error_response(
        request, ErrorCode.INTERNAL_ERROR, "Nastala neočakávaná chyba servera."
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
