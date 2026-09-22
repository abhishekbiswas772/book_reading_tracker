"""
Business logic for creating books. Deliberately kept out of the routes
layer so routes only deal with HTTP concerns and services only deal with
domain/DB concerns.
"""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book
from app.schemas.book import BookCreateRequest, BookResponse


class BookService:
    """
    Stateless service for Book operations. Kept as a singleton instance
    (module-level `book_service` below) since it holds no per-request state
    — every method takes the AsyncSession it needs to operate on.
    """

    class BookServiceException(Exception):
        """Raised when a book cannot be persisted due to a DB/storage failure."""

        pass

    class DuplicateBookError(Exception):
        """Raised when a book with the same title + author already exists."""

        pass

    _instance: "BookService | None" = None

    def __new__(cls) -> "BookService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def add_book(self, session: AsyncSession, payload: BookCreateRequest) -> BookResponse:
        """
        Persist a new book and return it (including the generated id).

        Field-level validation (empty title, bad status) is already handled
        by BookCreateRequest at the schema layer. This method additionally
        relies on the DB's UNIQUE(title, author) constraint (see
        app/db/models.py) to reject duplicates — checked here via
        IntegrityError rather than a separate SELECT, so it's race-safe
        under concurrent requests.
        """
        try:
            book = Book(
                title=payload.title,
                # DB stores "no author" as "" so the UNIQUE constraint applies to it too.
                author=payload.author or "",
                status=payload.status.value,
            )
            session.add(book)
            await session.commit()
            await session.refresh(book)
            return BookResponse.model_validate(book)
        except IntegrityError as exc:
            await session.rollback()
            raise BookService.DuplicateBookError(
                f"A book titled '{payload.title}'"
                + (f" by '{payload.author}'" if payload.author else "")
                + " already exists"
            ) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise BookService.BookServiceException(
                f"Could not save book to the database: {exc}"
            ) from exc
        except Exception as exc:
            await session.rollback()
            raise BookService.BookServiceException(
                f"Unexpected error while saving book: {exc}"
            ) from exc


book_service = BookService()
