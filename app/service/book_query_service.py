"""
Business logic for read/query operations on books: list, filter by status,
and per-status counts. Kept in its own service (separate from BookService,
which only handles the add-book write path) so the two slices don't
collide while being developed in parallel.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, BookStatus
from app.schemas.book import BookResponse
from app.schemas.book_query import StatusCountsResponse


class BookQueryService:
    """
    Stateless service for read-only Book queries. Kept as a singleton
    instance (module-level `book_query_service` below), following the same
    pattern as BookService.
    """

    class BookQueryServiceException(Exception):
        """Raised when books cannot be read/queried due to a DB/storage failure."""

        pass

    _instance: "BookQueryService | None" = None

    def __new__(cls) -> "BookQueryService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def list_books(
        self, session: AsyncSession, status: BookStatus | None = None
    ) -> list[BookResponse]:
        """
        Return all books, optionally filtered to a single status.

        Status validity is already enforced at the FastAPI query-param
        layer (typed as BookStatus), so `status` here is either None or
        one of the three valid values.
        """
        try:
            stmt = select(Book).order_by(Book.created_at.desc())
            if status is not None:
                stmt = stmt.where(Book.status == status.value)
            result = await session.execute(stmt)
            books = result.scalars().all()
            return [BookResponse.model_validate(book) for book in books]
        except SQLAlchemyError as exc:
            raise BookQueryService.BookQueryServiceException(
                f"Could not read books from the database: {exc}"
            ) from exc
        except Exception as exc:
            raise BookQueryService.BookQueryServiceException(
                f"Unexpected error while reading books: {exc}"
            ) from exc

    async def get_status_counts(self, session: AsyncSession) -> StatusCountsResponse:
        """
        Return the number of books per status, with every status present
        (defaulting to 0 if no books exist for it).
        """
        try:
            stmt = select(Book.status, func.count(Book.id)).group_by(Book.status)
            result = await session.execute(stmt)
            counts = {status_value: count for status_value, count in result.all()}
            return StatusCountsResponse(
                **{status.value: counts.get(status.value, 0) for status in BookStatus}
            )
        except SQLAlchemyError as exc:
            raise BookQueryService.BookQueryServiceException(
                f"Could not count books by status: {exc}"
            ) from exc
        except Exception as exc:
            raise BookQueryService.BookQueryServiceException(
                f"Unexpected error while counting books by status: {exc}"
            ) from exc


book_query_service = BookQueryService()
