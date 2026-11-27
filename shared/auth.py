"""Dočasná autentifikácia cez vývojové tokeny (Patch 01). Neskôr ju nahradí reálna služba."""
import hmac
import os

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from shared.errors import ApiError, ErrorCode

DEV_TOKENS_ENV = "EVALVO_DEV_TOKENS"

_bearer = HTTPBearer(
    auto_error=False,
    description="Zástupný vývojový token z EVALVO_DEV_TOKENS.",
)


class Identity(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str


def require_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    """Overí `Authorization: Bearer <token>` voči EVALVO_DEV_TOKENS ("token:user_id,...")."""
    unauthenticated = ApiError(
        ErrorCode.UNAUTHENTICATED,
        "Chýba alebo je neplatný prístupový token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthenticated

    for position, entry in enumerate(os.environ.get(DEV_TOKENS_ENV, "").split(","), start=1):
        if not entry.strip():
            continue
        token, separator, user_id = entry.strip().partition(":")
        if not separator or not token or not user_id:
            raise RuntimeError(f"{DEV_TOKENS_ENV}: neplatná položka č. {position}")
        if hmac.compare_digest(token.encode(), credentials.credentials.encode()):
            return Identity(user_id=user_id)

    raise unauthenticated
