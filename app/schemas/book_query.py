"""
Pydantic response schemas for read/query endpoints on the Book resource
(list, filter, status counts) built on top of the original add-book slice.

Reuses BookResponse from app.schemas.book rather than redefining it, per
the convention documented in CLAUDE.md / README.md.
"""

from pydantic import BaseModel, ConfigDict, Field


class StatusCountsResponse(BaseModel):
    """
    Count of books per status. Every status is always present in the
    response, defaulting to 0 if no books exist with that status.

    Field names use underscores (valid Python identifiers) but alias to
    the actual hyphenated status values ("to-read") for JSON in/out, so
    the wire format matches the `status` values used everywhere else in
    the API (e.g. {"to-read": 2, "reading": 1, "done": 0}).
    """

    model_config = ConfigDict(populate_by_name=True)

    to_read: int = Field(default=0, alias="to-read")
    reading: int = Field(default=0)
    done: int = Field(default=0)
