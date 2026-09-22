"""
Pydantic request schemas for updating/deleting a Book.

ASSUMPTION: reuses BookResponse from app.schemas.book (imported, not
redefined) for both the PATCH response and as the response type on the
DELETE route's underlying data, per the existing convention of sharing
response contracts across endpoints.
"""

from pydantic import BaseModel, field_validator, model_validator

from app.db.models import BookStatus
from app.schemas.book import BookResponse  # noqa: F401  (re-exported for convenience)


class BookUpdateRequest(BaseModel):
    """
    Body for PATCH /book/{book_id}. All fields are optional so callers can
    update any subset of title/author/status.

    ASSUMPTION: at least one field must be provided, or this is rejected as
    a 422 (via the app's existing RequestValidationError handler, which
    reshapes the error to `{"detail": ..., "field": ...}`) rather than
    silently no-op'ing on an empty body.
    """

    title: str | None = None
    author: str | None = None
    status: BookStatus | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank_if_provided(cls, value: str | None) -> str | None:
        if value is None:
            return None
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

    @model_validator(mode="after")
    def at_least_one_field_provided(self) -> "BookUpdateRequest":
        if self.title is None and self.author is None and self.status is None:
            raise ValueError("at least one of title, author, status must be provided")
        return self
