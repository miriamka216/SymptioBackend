"""Obálka správy pre broker. Iba model; odosielanie a outbox prídu neskôr."""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: UUID = Field(default_factory=uuid4)
    type: str = Field(pattern=EVENT_TYPE_PATTERN)
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
