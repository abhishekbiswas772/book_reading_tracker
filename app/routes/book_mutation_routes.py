"""
Book mutation routes (PATCH/DELETE). Class-based routing, same pattern as
BookRouter: BookMutationRouter encapsulates its own APIRouter instance and
registers its endpoint handlers as bound methods.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db_session
from app.schemas.book import BookResponse
from app.schemas.book_mutation import BookUpdateRequest
from app.service.book_mutation_service import BookMutationService, book_mutation_service


class BookMutationRouter:
    """Encapsulates the PATCH/DELETE /book/{book_id} routes and their dependencies."""

    def __init__(self, service: BookMutationService) -> None:
        self._service = service
        self.router = APIRouter(tags=["Books"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/book/{book_id}",
            self.update_book,
            methods=["PATCH"],
            response_model=BookResponse,
            status_code=status.HTTP_200_OK,
            summary="Partially update a book",
        )
        self.router.add_api_route(
            "/book/{book_id}",
            self.delete_book,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            summary="Delete a book",
        )

    async def update_book(
        self,
        book_id: str,
        payload: BookUpdateRequest,
        session: AsyncSession = Depends(get_db_session),
    ) -> BookResponse:
        """
        PATCH /book/{book_id}

        Field-level validation (empty title / bad status / wrong types /
        empty body) is handled by BookUpdateRequest and surfaces as a 422
        via the RequestValidationError handler registered in main.py.
        """
        try:
            return await self._service.update_book(session, book_id, payload)
        except BookMutationService.BookNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except BookMutationService.DuplicateBookError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except BookMutationService.BookMutationServiceException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    async def delete_book(
        self,
        book_id: str,
        session: AsyncSession = Depends(get_db_session),
    ) -> None:
        """
        DELETE /book/{book_id}

        Returns 204 No Content on success (no body).
        """
        try:
            await self._service.delete_book(session, book_id)
        except BookMutationService.BookNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except BookMutationService.BookMutationServiceException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


book_mutation_router = BookMutationRouter(service=book_mutation_service)
