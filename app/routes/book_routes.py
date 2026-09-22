"""
Book routes. Class-based routing: BookRouter encapsulates its own
APIRouter instance and registers its endpoint handlers as bound methods,
so all book-related routing lives in one cohesive object.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db_session
from app.schemas.book import BookCreateRequest, BookResponse
from app.service.book_service import BookService, book_service


class BookRouter:
    """Encapsulates all /book routes and their dependencies."""

    def __init__(self, service: BookService) -> None:
        self._service = service
        self.router = APIRouter(tags=["Books"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/book",
            self.add_book,
            methods=["POST"],
            response_model=BookResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Add a book to the reading list",
        )

    async def add_book(
        self,
        payload: BookCreateRequest,
        session: AsyncSession = Depends(get_db_session),
    ) -> BookResponse:
        """
        POST /book

        Field-level validation (empty title / bad status / wrong types) is
        handled by BookCreateRequest and surfaces as a 422 via the
        RequestValidationError handler registered in main.py.
        """
        try:
            return await self._service.add_book(session, payload)
        except BookService.DuplicateBookError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except BookService.BookServiceException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


book_router = BookRouter(service=book_service)
