"""Stránkovanie kolekcií podľa API.md: cursor z next_cursor a limit 1–100, predvolene 20."""
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

T = TypeVar("T")


class PaginationParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    cursor: str | None
    limit: int


def pagination_params(
    cursor: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PaginationParams:
    return PaginationParams(cursor=cursor, limit=limit)


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
