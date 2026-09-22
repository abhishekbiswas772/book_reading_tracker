"""POST /book — happy paths, 422 validation, 409 duplicates."""

import pytest

from app.db.models import Book

pytestmark = pytest.mark.asyncio


async def test_create_full_body(client):
    resp = await client.post(
        "/book",
        json={"title": "Dune", "author": "Frank Herbert", "status": "to-read"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Dune"
    assert body["author"] == "Frank Herbert"
    assert body["status"] == "to-read"
    assert body["id"]
    assert body["created_at"] == body["updated_at"]


async def test_create_without_author(client):
    resp = await client.post("/book", json={"title": "Dune", "status": "to-read"})
    assert resp.status_code == 201
    assert resp.json()["author"] is None


async def test_create_whitespace_author_becomes_none(client):
    resp = await client.post(
        "/book", json={"title": "Dune", "author": "   ", "status": "to-read"}
    )
    assert resp.status_code == 201
    assert resp.json()["author"] is None


async def test_create_title_is_trimmed(client):
    resp = await client.post("/book", json={"title": "  Dune  ", "status": "to-read"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Dune"


@pytest.mark.parametrize("status_value", ["to-read", "reading", "done"])
async def test_create_accepts_all_statuses(client, status_value):
    resp = await client.post(
        "/book", json={"title": f"Book {status_value}", "status": status_value}
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == status_value


async def test_create_missing_title(client):
    resp = await client.post("/book", json={"status": "to-read"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "title"


async def test_create_missing_status(client):
    resp = await client.post("/book", json={"title": "Dune"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_create_empty_title(client):
    resp = await client.post("/book", json={"title": "   ", "status": "to-read"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["field"] == "title"
    assert "title must not be empty" in body["detail"]


async def test_create_title_wrong_type(client):
    resp = await client.post("/book", json={"title": 123, "status": "to-read"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "title"


async def test_create_invalid_status(client):
    resp = await client.post("/book", json={"title": "Dune", "status": "reading-now"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["field"] == "status"
    assert "Input should be 'to-read', 'reading' or 'done'" in body["detail"]


async def test_create_null_status(client):
    resp = await client.post("/book", json={"title": "Dune", "status": None})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_create_malformed_json_body(client):
    resp = await client.post(
        "/book", content=b"{not valid json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 422
    # A JSON-decode error's loc is ("body", <char offset>), not ("body", "<field>"),
    # so after the location-prefix strip in main.py it's the offset's own string form,
    # not "unknown" (that value is reserved for the model_validator "unknown field" case).
    body = resp.json()
    assert body["field"].isdigit()
    assert "JSON decode error" in body["detail"]


async def test_create_author_wrong_type(client):
    resp = await client.post(
        "/book", json={"title": "Dune", "author": 42, "status": "to-read"}
    )
    assert resp.status_code == 422
    assert resp.json()["field"] == "author"


async def test_create_exact_duplicate(client):
    payload = {"title": "Dune", "author": "Frank Herbert", "status": "to-read"}
    first = await client.post("/book", json=payload)
    assert first.status_code == 201
    second = await client.post("/book", json=payload)
    assert second.status_code == 409
    assert (
        second.json()["detail"] == "A book titled 'Dune' by 'Frank Herbert' already exists"
    )


async def test_create_case_insensitive_duplicate(client):
    await client.post(
        "/book", json={"title": "Dune", "author": "Frank Herbert", "status": "to-read"}
    )
    resp = await client.post(
        "/book", json={"title": "dune", "author": "FRANK HERBERT", "status": "reading"}
    )
    assert resp.status_code == 409


async def test_create_same_title_different_author_succeeds(client):
    await client.post(
        "/book", json={"title": "Dune", "author": "Frank Herbert", "status": "to-read"}
    )
    resp = await client.post(
        "/book", json={"title": "Dune", "author": "Someone Else", "status": "to-read"}
    )
    assert resp.status_code == 201


async def test_create_same_title_no_author_twice_conflicts(client):
    first = await client.post("/book", json={"title": "Dune", "status": "to-read"})
    assert first.status_code == 201
    second = await client.post("/book", json={"title": "Dune", "status": "reading"})
    assert second.status_code == 409


async def test_create_same_title_one_with_author_one_without_succeeds(client):
    await client.post("/book", json={"title": "Dune", "status": "to-read"})
    resp = await client.post(
        "/book", json={"title": "Dune", "author": "Frank Herbert", "status": "to-read"}
    )
    assert resp.status_code == 201


async def test_create_conflicts_with_preinserted_row(client, raw_session):
    raw_session.add(Book(title="Dune", author="Frank Herbert", status="to-read"))
    await raw_session.commit()

    resp = await client.post(
        "/book", json={"title": "Dune", "author": "Frank Herbert", "status": "reading"}
    )
    assert resp.status_code == 409
