"""
Read/query routes for books: list all, filter by status, and per-status
counts. Class-based routing, following the same pattern as BookRouter in
app/routes/book_routes.py — this router owns its own APIRouter and
registers its handlers as bound methods.

NOTE: kept in a separate router/module from BookRouter (rather than adding
to book_routes.py) so this slice can be developed in parallel with other
work on the existing routes without touching that file. Wire it into the
app the same way as book_router:

    from app.routes.book_query_routes import book_query_router
    app.include_router(book_query_router.router)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db_session
from app.db.models import BookStatus
from app.schemas.book import BookResponse
from app.schemas.book_query import StatusCountsResponse
from app.service.book_query_service import BookQueryService, book_query_service


class BookQueryRouter:
    """Encapsulates all read/query /book routes and their dependencies."""

    def __init__(self, service: BookQueryService) -> None:
        self._service = service
        self.router = APIRouter(tags=["Books"])
        self._register_routes()

    def _register_routes(self) -> None:
        # Registered before the plain "/book" GET is irrelevant here since
        # "/book/status-counts" and "/book" are distinct static paths (no
        # path params involved), but it's listed first for readability.
        self.router.add_api_route(
            "/book/status-counts",
            self.get_status_counts,
            methods=["GET"],
            response_model=StatusCountsResponse,
            status_code=status.HTTP_200_OK,
            summary="Get the count of books per status",
        )
        self.router.add_api_route(
            "/book",
            self.list_books,
            methods=["GET"],
            response_model=list[BookResponse],
            status_code=status.HTTP_200_OK,
            summary="List books, optionally filtered by status",
        )

    async def list_books(
        self,
        status_filter: BookStatus | None = Query(
            default=None,
            alias="status",
            description="Optional status to filter by: one of 'to-read', 'reading', 'done'.",
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> list[BookResponse]:
        """
        GET /book
        GET /book?status=to-read

        An invalid `status` value (not one of 'to-read', 'reading', 'done')
        is rejected with a 422 naming the field, via the same
        RequestValidationError handler registered in main.py that POST
        /book already uses.
        """
        try:
            return await self._service.list_books(session, status_filter)
        except BookQueryService.BookQueryServiceException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    async def get_status_counts(
        self,
        session: AsyncSession = Depends(get_db_session),
    ) -> StatusCountsResponse:
        """
        GET /book/status-counts

        Returns the count of books for each of the three statuses,
        including statuses with zero books.
        """
        try:
            return await self._service.get_status_counts(session)
        except BookQueryService.BookQueryServiceException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


book_query_router = BookQueryRouter(service=book_query_service)
