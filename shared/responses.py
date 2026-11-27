"""Spoločný základ odpovede 202 Accepted. ID pole (download_id, job_id, ...) pridá služba."""
from pydantic import BaseModel


class AcceptedResponse(BaseModel):
    status: str
    status_url: str
