"""Načítanie a kontrola hlavičky Idempotency-Key. Ukladanie a 409 prídu neskôr."""
from typing import Annotated

from fastapi import Depends, Header

from shared.errors import ApiError, ErrorCode, FieldError

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
MAX_IDEMPOTENCY_KEY_LENGTH = 255


def _invalid(reason: str) -> ApiError:
    return ApiError(
        ErrorCode.VALIDATION_ERROR,
        "Požiadavka obsahuje neplatnú hodnotu.",
        details={"fields": [FieldError(field=IDEMPOTENCY_KEY_HEADER, reason=reason).model_dump()]},
    )


def optional_idempotency_key(
    key: Annotated[str | None, Header(alias=IDEMPOTENCY_KEY_HEADER)] = None,
) -> str | None:
    if key is None:
        return None
    if not key.strip():
        raise _invalid("Hodnota je prázdna.")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise _invalid(f"Hodnota je príliš dlhá (max. {MAX_IDEMPOTENCY_KEY_LENGTH} znakov).")
    return key


def require_idempotency_key(
    key: Annotated[str | None, Depends(optional_idempotency_key)],
) -> str:
    if key is None:
        raise _invalid("Hlavička chýba.")
    return key
