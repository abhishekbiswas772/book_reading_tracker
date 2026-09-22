# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FastAPI backend for a "Reading List Tracker". Implements full CRUD plus
filtering/aggregation:
- `POST /book` — add a book
- `GET /book` (optional `?status=`) — list/filter
- `GET /book/status-counts` — count per status (all 3 always present)
- `PATCH /book/{book_id}` — partial update (title/author/status)
- `DELETE /book/{book_id}` — delete (`204`)

Data model — a `Book` has:
- `title` (string, required, non-empty)
- `author` (string, optional)
- `status` (string, required, exactly one of `to-read`, `reading`, `done`)
- `id` (string UUID, server-generated)
- `created_at` / `updated_at` (datetime, DB-generated)

A book is a duplicate (rejected with `409`) if it shares the same `title`
AND `author` (case-insensitive) with an existing row — enforced by a DB-level
unique constraint, not just an app-level check. Indexes exist on `title`,
`author`, `status`, and `created_at` individually for future search/filter
endpoints.

## Commands

```bash
# setup
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# run (auto-creates SQLite tables on startup)
uvicorn main:app --reload --port 8000

# docs
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

There is no test suite, linter, or build step configured in this repo yet.
There is also no migration tooling — if `app/db/models.py` changes (new
column/constraint), delete the local `reading_list.db` file and let
`DatabaseHandler.init_models()` recreate it on next startup.

Manual verification (used in place of automated tests):

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"title": "Dune", "author": "Frank Herbert", "status": "to-read"}'
```

## Architecture

Layering is strict and one-directional: **routes → service → db**. Routes
never talk to the database directly, and business logic never lives in the
routes layer.

```
main.py                     # app entry point (outside app/), lifespan hooks, Swagger config,
                             # global RequestValidationError handler, includes all 3 routers
app/
  config/config.py          # pydantic-settings Settings (app_name, port, database_url, ...),
                             # cached via get_settings()
  db/
    config.py               # DatabaseHandler — singleton owning the async SQLAlchemy engine
                             # + async_sessionmaker; get_db_session() is the FastAPI dependency
                             # every router should use to get an AsyncSession
    models.py                # SQLAlchemy async ORM models (Book, BookStatus enum)
  schemas/
    book.py                  # BookCreateRequest, BookResponse (POST /book)
    book_query.py             # StatusCountsResponse (GET endpoints)
    book_mutation.py          # BookUpdateRequest (PATCH)
  service/
    book_service.py          # BookService — add-book logic
    book_query_service.py     # BookQueryService — list/filter/status-counts logic
    book_mutation_service.py  # BookMutationService — update/delete logic
  routes/
    book_routes.py           # BookRouter — POST /book
    book_query_routes.py      # BookQueryRouter — GET /book, GET /book/status-counts
    book_mutation_routes.py   # BookMutationRouter — PATCH/DELETE /book/{book_id}
```

The create/query/mutation slices are deliberately split into separate
schema/service/route modules (rather than all growing `book_*.py`) so they
can be developed in parallel without colliding on the same files — this was
literally how they were built (by separate parallel agents). All routers
are wired together only in `main.py`.

Key conventions established in this codebase (follow these for new endpoints/modules):

- **Class-based routing**: a router is a class (e.g. `BookRouter`) that builds its own
  `APIRouter` in `__init__` and registers routes via `add_api_route`, not with `@router.post`
  decorators. Instantiate a module-level singleton (e.g. `book_router = BookRouter(...)`) and
  `include_router(book_router.router)` in `main.py`.
- **Singletons via `__new__`**: `DatabaseHandler` and `BookService` are singletons implemented
  with `__new__`, each with a nested `<ClassName>Exception` for its own failure domain
  (`DatabaseHandler.DatabaseHandlerException`, `BookService.BookServiceException`).
- **All I/O wrapped in try/except**: service methods catch `SQLAlchemyError` (and a broad
  `Exception` fallback) and re-raise as the class's own exception type; routes catch that
  service exception and convert it to an `HTTPException`.
- **Validation errors name the bad field**: don't rely on FastAPI's default verbose 422 body.
  The global handler in `main.py` (`validation_exception_handler`) reshapes
  `RequestValidationError` into `{"detail": "...", "field": "<field_name>"}` — it strips the
  `body`/`query`/`path` location prefix from pydantic's `loc`, so this works the same whether
  the bad field came from a JSON body or a `?query=param`. Field-level invariants (e.g.
  non-empty `title`) belong in pydantic `field_validator`s on the schema in `app/schemas/`, not
  in the service layer. A `model_validator` (not a single-field one) produces `field: "unknown"`
  since there's no one offending field — see `BookUpdateRequest`'s "at least one field" check.
- **Service exceptions map 1:1 to HTTP status in the route layer**: e.g.
  `BookMutationService.BookNotFoundError` → 404, `DuplicateBookError` → 409,
  `BookMutationServiceException` → 400. Each service defines its own nested exception classes
  (don't reuse another service's exception classes across modules).
- **After a SQLAlchemy `rollback()`, don't read ORM-managed attributes off the entity
  synchronously** (e.g. `book.title`) — rollback expires them, and a lazy-load in an
  `AsyncSession` without an `await` raises `MissingGreenlet` rather than reloading. Capture any
  values you'll need in an error message *before* the write attempt, or re-fetch with an
  explicit `await session.refresh(...)` / new query.
- **IDs are server-generated UUID strings** (not autoincrement ints), assigned as the SQLAlchemy
  column default in `app/db/models.py`.
- **`status` is stored as a `String` with a SQL `CHECK` constraint**, not a native SQL enum type,
  for portability across DB backends — SQLite has no native enum type anyway.
- Async everywhere: SQLAlchemy via `sqlalchemy.ext.asyncio` (`create_async_engine`,
  `AsyncSession`, `async_sessionmaker`), driver is `aiosqlite`.
- `app/schemas/` was added beyond the originally-specified folder set to hold shared
  pydantic request/response contracts reusable by future endpoints (e.g. import
  `BookResponse` for a list/filter endpoint rather than redefining it).

## Extending this codebase

When adding new endpoints:
- Reuse `get_db_session` from `app/db/config.py` for the `AsyncSession` dependency.
- Reuse `Book` / `BookStatus` from `app/db/models.py`.
- Reuse or extend `BookResponse` from `app/schemas/book.py`.
- Put business logic in a new or extended service class under `app/service/`, not in routes.
- Register any new router class instance in `main.py` via `app.include_router(...)`.
- No frontend exists yet. If one is added, it should be plain HTML/CSS/JS served as static
  files directly from this FastAPI app (no separate frontend server/build step) — check
  README.md for whether this has since been added and where.
