"""GET /book (list/filter) and GET /book/status-counts."""

import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_empty(client):
    resp = await client.get("/book")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_multiple_ordered_desc_by_created_at(client):
    await client.post("/book", json={"title": "First", "status": "to-read"})
    await asyncio.sleep(1.1)  # SQLite func.now() is second-resolution
    await client.post("/book", json={"title": "Second", "status": "to-read"})

    resp = await client.get("/book")
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()]
    assert titles == ["Second", "First"]


async def test_list_author_null_when_unset(client):
    await client.post("/book", json={"title": "Dune", "status": "to-read"})
    resp = await client.get("/book")
    assert resp.json()[0]["author"] is None


async def test_list_id_is_uuid_format(client):
    await client.post("/book", json={"title": "Dune", "status": "to-read"})
    resp = await client.get("/book")
    book_id = resp.json()[0]["id"]
    assert len(book_id) == 36
    assert book_id.count("-") == 4


async def test_list_filter_by_status(client):
    await client.post("/book", json={"title": "A", "status": "to-read"})
    await client.post("/book", json={"title": "B", "status": "reading"})
    await client.post("/book", json={"title": "C", "status": "reading"})

    resp = await client.get("/book", params={"status": "reading"})
    assert resp.status_code == 200
    titles = {b["title"] for b in resp.json()}
    assert titles == {"B", "C"}


async def test_list_filter_no_matches(client):
    await client.post("/book", json={"title": "A", "status": "to-read"})
    resp = await client.get("/book", params={"status": "done"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_no_param_lists_all(client):
    await client.post("/book", json={"title": "A", "status": "to-read"})
    await client.post("/book", json={"title": "B", "status": "done"})
    resp = await client.get("/book")
    assert len(resp.json()) == 2


async def test_list_invalid_status_filter(client):
    resp = await client.get("/book", params={"status": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_list_empty_status_filter(client):
    resp = await client.get("/book", params={"status": ""})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_list_wrong_case_status_filter(client):
    resp = await client.get("/book", params={"status": "TO-READ"})
    assert resp.status_code == 422
    assert resp.json()["field"] == "status"


async def test_status_counts_empty(client):
    resp = await client.get("/book/status-counts")
    assert resp.status_code == 200
    assert resp.json() == {"to-read": 0, "reading": 0, "done": 0}


async def test_status_counts_mixed(client):
    await client.post("/book", json={"title": "A", "status": "to-read"})
    await client.post("/book", json={"title": "B", "status": "to-read"})
    await client.post("/book", json={"title": "C", "status": "reading"})

    resp = await client.get("/book/status-counts")
    body = resp.json()
    assert body == {"to-read": 2, "reading": 1, "done": 0}


async def test_status_counts_always_has_three_keys(client):
    await client.post("/book", json={"title": "A", "status": "done"})
    resp = await client.get("/book/status-counts")
    body = resp.json()
    assert set(body.keys()) == {"to-read", "reading", "done"}
