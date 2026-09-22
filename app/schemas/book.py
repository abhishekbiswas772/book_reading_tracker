"""
Pydantic request/response schemas for the Book resource.

ASSUMPTION: schemas live in their own app/schemas package (not listed in the
original folder rules) so routes and service layers can share the same
request/response contracts without duplicating them. Safe for other
engineers to import BookResponse for their own read/list/filter endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.models import BookStatus


class BookCreateRequest(BaseModel):
    title: str
    author: str | None = None
    status: BookStatus

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped

    @field_validator("author")
    @classmethod
    def blank_author_becomes_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    author: str | None
    status: BookStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("author", mode="before")
    @classmethod
    def empty_string_author_becomes_none(cls, value: str | None) -> str | None:
        # DB stores "no author" as "" (see app/db/models.py) so the UNIQUE
        # constraint on (title, author) is meaningful; translate it back to
        # None here so API responses match the request contract.
        return value or None
