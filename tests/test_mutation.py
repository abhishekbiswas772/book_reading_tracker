"""PATCH /book/{book_id} and DELETE /book/{book_id}."""

import asyncio

import pytest

from app.db.models import Book

pytestmark = pytest.mark.asyncio


async def _create(client, **overrides):
    payload = {"title": "Dune", "author": "Frank Herbert", "status": "to-read"}
    payload.update(overrides)
    resp = await client.post("/book", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def test_patch_title_only(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"title": "Dune Messiah"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Dune Messiah"
    assert body["author"] == "Frank Herbert"
    assert body["status"] == "to-read"
    assert body["created_at"] == book["created_at"]


async def test_patch_author_only(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"author": "F. Herbert"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["author"] == "F. Herbert"
    assert body["title"] == "Dune"


async def test_patch_status_only(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"status": "reading"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "reading"


async def test_patch_multiple_fields(client):
    book = await _create(client)
    resp = await client.patch(
        f"/book/{book['id']}", json={"title": "New Title", "status": "done"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New Title"
    assert body["status"] == "done"


async def test_patch_updated_at_advances_created_at_unchanged(client):
    book = await _create(client)
    await asyncio.sleep(1.1)  # SQLite func.now() is second-resolution
    resp = await client.patch(f"/book/{book['id']}", json={"status": "done"})
    body = resp.json()
    assert body["updated_at"] > book["updated_at"]
    assert body["created_at"] == book["created_at"]


async def test_patch_status_only_leaves_author_unchanged(client):
    book = await _create(client, author="Frank Herbert")
    resp = await client.patch(f"/book/{book['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["author"] == "Frank Herbert"


async def test_patch_whitespace_author_alongside_other_field_leaves_author_untouched(client):
    # A whitespace-only author alone would trip the "at least one field" model
    # validator (it resolves to None, same as not sending it at all), so pair it
    # with a real field change to observe the "don't touch" behavior in isolation.
    book = await _create(client, author="Frank Herbert")
    resp = await client.patch(
        f"/book/{book['id']}", json={"title": "Dune Messiah", "author": "   "}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Dune Messiah"
    assert body["author"] == "Frank Herbert"


async def test_patch_empty_body(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["field"] == "unknown"
    assert "at least one of title, author, status must be provided" in body["detail"]


async def test_patch_all_fields_null(client):
    book = await _create(client)
    resp = await client.patch(
        f"/book/{book['id']}", json={"title": None, "author": None, "status": None}
    )
    assert resp.status_code == 422
    assert resp.json()["field"] == "unknown"


async def test_patch_whitespace_title(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"title": "   "})
    assert resp.status_code == 422
    assert resp.json()["field"] == "title"


async def test_patch_invalid_status(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"status": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_patch_wrong_type(client):
    book = await _create(client)
    resp = await client.patch(f"/book/{book['id']}", json={"title": 123})
    assert resp.status_code == 422
    assert resp.json()["field"] == "title"


async def test_patch_nonexistent_book(client):
    resp = await client.patch("/book/does-not-exist", json={"title": "X"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "No book found with id 'does-not-exist'"}


async def test_patch_garbage_non_uuid_id(client):
    resp = await client.patch("/book/%%%not-a-uuid%%%", json={"title": "X"})
    assert resp.status_code == 404


async def test_patch_collides_with_existing_book(client):
    await _create(client, title="Dune", author="Frank Herbert")
    other = await _create(client, title="Other Book", author="Someone")
    resp = await client.patch(
        f"/book/{other['id']}", json={"title": "Dune", "author": "Frank Herbert"}
    )
    assert resp.status_code == 409


async def test_patch_collides_case_insensitively(client):
    await _create(client, title="Dune", author="Frank Herbert")
    other = await _create(client, title="Other Book", author="Someone")
    resp = await client.patch(
        f"/book/{other['id']}", json={"title": "dune", "author": "FRANK HERBERT"}
    )
    assert resp.status_code == 409


async def test_patch_collides_with_preinserted_row(client, raw_session):
    raw_session.add(Book(title="Dune", author="Frank Herbert", status="to-read"))
    await raw_session.commit()

    other = await _create(client, title="Other Book", author="Someone")
    resp = await client.patch(
        f"/book/{other['id']}", json={"title": "Dune", "author": "Frank Herbert"}
    )
    assert resp.status_code == 409


async def test_patch_to_own_current_values_is_not_a_false_conflict(client):
    book = await _create(client)
    resp = await client.patch(
        f"/book/{book['id']}", json={"title": book["title"], "author": book["author"]}
    )
    assert resp.status_code == 200


async def test_delete_existing_book(client):
    book = await _create(client)
    resp = await client.delete(f"/book/{book['id']}")
    assert resp.status_code == 204
    assert resp.content == b""

    listing = await client.get("/book")
    assert listing.json() == []
    counts = await client.get("/book/status-counts")
    assert counts.json()["to-read"] == 0


async def test_delete_nonexistent_book(client):
    resp = await client.delete("/book/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "No book found with id 'does-not-exist'"}


async def test_delete_twice(client):
    book = await _create(client)
    first = await client.delete(f"/book/{book['id']}")
    assert first.status_code == 204
    second = await client.delete(f"/book/{book['id']}")
    assert second.status_code == 404
