"""
Business logic for updating/deleting books. Kept in its own service module
(rather than extending BookService) since this is a separate workstream
being developed in parallel with list/filter/aggregation endpoints, and
per the CLAUDE.md convention: business logic lives in the service layer,
not in routes.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book
from app.schemas.book import BookResponse
from app.schemas.book_mutation import BookUpdateRequest


class BookMutationService:
    """
    Stateless service for update/delete Book operations. Kept as a
    singleton instance (module-level `book_mutation_service` below), same
    pattern as BookService.
    """

    class BookMutationServiceException(Exception):
        """Raised when a book cannot be updated/deleted due to a DB/storage failure."""

        pass

    class BookNotFoundError(Exception):
        """Raised when the requested book_id does not exist."""

        pass

    class DuplicateBookError(Exception):
        """Raised when an update would collide with another row's (title, author)."""

        pass

    _instance: "BookMutationService | None" = None

    def __new__(cls) -> "BookMutationService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _get_book_or_raise(self, session: AsyncSession, book_id: str) -> Book:
        result = await session.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if book is None:
            raise BookMutationService.BookNotFoundError(
                f"No book found with id '{book_id}'"
            )
        return book

    async def update_book(
        self, session: AsyncSession, book_id: str, payload: BookUpdateRequest
    ) -> BookResponse:
        """
        Partially update a book. Only fields explicitly provided in the
        payload are changed. Relies on the DB's UNIQUE(title, author)
        constraint (see app/db/models.py) to reject collisions with a
        different existing row, checked via IntegrityError so it's
        race-safe under concurrent requests. `updated_at` is refreshed
        automatically by the DB's onupdate=func.now() clause.
        """
        # Captured before any DB write so the duplicate-conflict message
        # below never has to touch `book`'s attributes after a rollback
        # (rollback expires ORM-managed attributes; a plain sync attribute
        # access on an expired attribute in an AsyncSession can raise
        # MissingGreenlet instead of the intended message).
        pre_update_title = None
        try:
            book = await self._get_book_or_raise(session, book_id)
            pre_update_title = book.title

            if payload.title is not None:
                book.title = payload.title
            if payload.author is not None:
                # DB stores "no author" as "" so the UNIQUE constraint applies to it too.
                book.author = payload.author
            if payload.status is not None:
                book.status = payload.status.value

            await session.commit()
            await session.refresh(book)
            return BookResponse.model_validate(book)
        except BookMutationService.BookNotFoundError:
            raise
        except IntegrityError as exc:
            await session.rollback()
            raise BookMutationService.DuplicateBookError(
                f"A book titled '{payload.title or pre_update_title}'"
                + (f" by '{payload.author}'" if payload.author else "")
                + " already exists"
            ) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise BookMutationService.BookMutationServiceException(
                f"Could not update book in the database: {exc}"
            ) from exc
        except Exception as exc:
            await session.rollback()
            raise BookMutationService.BookMutationServiceException(
                f"Unexpected error while updating book: {exc}"
            ) from exc

    async def delete_book(self, session: AsyncSession, book_id: str) -> None:
        """
        Delete a book by id. Raises BookNotFoundError if it doesn't exist.
        """
        try:
            book = await self._get_book_or_raise(session, book_id)
            await session.delete(book)
            await session.commit()
        except BookMutationService.BookNotFoundError:
            raise
        except SQLAlchemyError as exc:
            await session.rollback()
            raise BookMutationService.BookMutationServiceException(
                f"Could not delete book from the database: {exc}"
            ) from exc
        except Exception as exc:
            await session.rollback()
            raise BookMutationService.BookMutationServiceException(
                f"Unexpected error while deleting book: {exc}"
            ) from exc


book_mutation_service = BookMutationService()
