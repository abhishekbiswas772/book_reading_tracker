# Reading List Tracker — Backend

FastAPI backend for a Reading List Tracker. Implements full CRUD plus
filtering/aggregation on the Book resource: create, list/filter, per-status
counts, partial update, and delete.

## Data model

A `Book` has:

| field      | type     | required  | notes                                                      |
|------------|----------|-----------|-------------------------------------------------------------|
| id         | string   | generated | UUID, assigned by the server on creation                   |
| title      | string   | yes       | must be non-empty (whitespace-only is rejected)             |
| author     | string   | no        | optional                                                    |
| status     | string   | yes       | one of exactly: `to-read`, `reading`, `done`                |
| created_at | datetime | generated | set by the DB when the row is inserted                     |
| updated_at | datetime | generated | set by the DB on insert, refreshed by the DB on any update  |

**Duplicates are rejected.** A book is considered a duplicate of an existing
one if it has the same `title` **and** the same `author`, compared
case-insensitively (e.g. `"Dune"`/`"dune"` by `"Frank Herbert"` collide; the
same title by a *different* author, or with no author at all, is allowed as
a separate entry). This is enforced with a database-level unique constraint,
so it also holds under concurrent requests — attempting to add a duplicate
returns `409 Conflict`.

**Indexes** exist on `title`, `author`, `status`, and `created_at`
individually (in addition to the composite unique index on `title`+`author`)
so a future search/filter/sort endpoint can query any of these columns
without a full table scan.

## API endpoints

| Method | Path                | Purpose                                    |
|--------|---------------------|---------------------------------------------|
| POST   | `/book`             | Add a book                                 |
| GET    | `/book`             | List books (optional `?status=` filter)    |
| GET    | `/book/status-counts` | Count of books per status (always all 3) |
| PATCH  | `/book/{book_id}`   | Partially update a book (title/author/status) |
| DELETE | `/book/{book_id}`   | Delete a book (`204` on success)           |

## Project structure

```
main.py                     # app entry point (uvicorn target: main:app)
app/
  config/
    config.py                # pydantic Settings (app name, port, db url, ...)
  db/
    config.py                 # async engine/session (DatabaseHandler singleton) + Base
    models.py                 # SQLAlchemy async ORM model: Book, BookStatus
  schemas/
    book.py                   # pydantic schemas for POST /book (BookCreateRequest, BookResponse)
    book_query.py              # pydantic schema for GET endpoints (StatusCountsResponse)
    book_mutation.py           # pydantic schema for PATCH (BookUpdateRequest)
  service/
    book_service.py           # BookService — add-book business logic
    book_query_service.py      # BookQueryService — list/filter/status-counts business logic
    book_mutation_service.py   # BookMutationService — update/delete business logic
  routes/
    book_routes.py            # BookRouter — class-based POST /book route
    book_query_routes.py       # BookQueryRouter — GET /book, GET /book/status-counts
    book_mutation_routes.py    # BookMutationRouter — PATCH/DELETE /book/{book_id}
```

Each slice (create / query / mutation) is deliberately split into its own
schema/service/route module rather than growing the original `book_*.py`
files, so parallel workstreams don't collide on the same files. All four
routers are wired together in `main.py`.

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Optional `.env` overrides (all have sensible defaults):

```
APP_NAME=Reading List Tracker
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./reading_list.db
DB_ECHO=false
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

On startup the SQLite tables are created automatically (`reading_list.db` in
the project root) — no separate migration step needed for this slice. There
is no migration tooling, so if the model schema changes (new column, new
constraint), delete `reading_list.db` and let it regenerate.

## API docs

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

## Try it with curl

**Success:**

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"title": "Dune", "author": "Frank Herbert", "status": "to-read"}'
```

Response (`201 Created`):

```json
{
  "id": "3f1b2c4e-....",
  "title": "Dune",
  "author": "Frank Herbert",
  "status": "to-read",
  "created_at": "2026-09-22T12:53:59",
  "updated_at": "2026-09-22T12:53:59"
}
```

**Duplicate book (409):**

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"title": "Dune", "author": "Frank Herbert", "status": "to-read"}'
```

```json
{
  "detail": "A book titled 'Dune' by 'Frank Herbert' already exists"
}
```

**Missing title (422):**

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"status": "to-read"}'
```

```json
{
  "detail": "Invalid value for field 'title': Field required",
  "field": "title"
}
```

**Empty title (422):**

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"title": "   ", "status": "to-read"}'
```

```json
{
  "detail": "Invalid value for field 'title': Value error, title must not be empty",
  "field": "title"
}
```

**Invalid status (422):**

```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{"title": "Dune", "status": "reading-now"}'
```

```json
{
  "detail": "Invalid value for field 'status': Input should be 'to-read', 'reading' or 'done'",
  "field": "status"
}
```

**List all books:**

```bash
curl http://localhost:8000/book
```

**Filter by status:**

```bash
curl "http://localhost:8000/book?status=reading"
```

**Invalid status filter (422):**

```bash
curl "http://localhost:8000/book?status=bogus"
```

```json
{
  "detail": "Invalid value for field 'status': Input should be 'to-read', 'reading' or 'done'",
  "field": "status"
}
```

**Counts per status:**

```bash
curl http://localhost:8000/book/status-counts
```

```json
{"to-read": 2, "reading": 1, "done": 0}
```

**Update a book (any subset of title/author/status):**

```bash
curl -X PATCH http://localhost:8000/book/<id> \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

Response (`200`): the updated book, with `updated_at` refreshed automatically.
An empty body is rejected with `422`. A nonexistent id returns `404`. If the
update would collide with another existing (title, author) pair, `409`.

**Delete a book:**

```bash
curl -X DELETE http://localhost:8000/book/<id>
```

`204 No Content` on success; `404` if the id doesn't exist.

## Notes for engineers building the frontend / further endpoints

- Import `get_db_session` from `app.db.config` to get an `AsyncSession` via FastAPI `Depends`.
- Import `Book` / `BookStatus` from `app.db.models` for the ORM model and status enum.
- Import `BookResponse` from `app.schemas.book` to reuse the same response shape.
- Register any new router in `main.py` the same way the existing routers are included.
