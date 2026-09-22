"""
Application entry point. Deliberately kept outside the app/ package.

Run with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config.config import get_settings
from app.db.config import DatabaseHandler
from app.routes.book_mutation_routes import book_mutation_router
from app.routes.book_query_routes import book_query_router
from app.routes.book_routes import book_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await DatabaseHandler().init_models()
    except DatabaseHandler.DatabaseHandlerException as exc:
        # Fail fast and loudly if the DB can't be prepared at startup.
        raise RuntimeError(f"Database startup failed: {exc}") from exc
    yield
    await DatabaseHandler().dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Reading List Tracker API",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Turns pydantic's default verbose error list into a single clear
    message naming the offending field, e.g.:
        {"detail": "Invalid value for field 'status': ...", "field": "status"}
    """
    first_error = exc.errors()[0]
    # loc is typically ("body"|"query"|"path", "<field_name>") — drop that
    # location-kind prefix so e.g. a bad ?status= query param reports as
    # "status", not "query.status".
    field_path = [
        str(part) for part in first_error["loc"] if part not in ("body", "query", "path")
    ]
    field_name = ".".join(field_path) if field_path else "unknown"
    message = first_error.get("msg", "Invalid input")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": f"Invalid value for field '{field_name}': {message}",
            "field": field_name,
        },
    )


app.include_router(book_router.router)
app.include_router(book_query_router.router)
app.include_router(book_mutation_router.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
