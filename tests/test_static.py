"""Static file serving via StaticFiles(directory="static", html=True)."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_index_served_at_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<title>Reading List Tracker</title>" in resp.text


async def test_style_css_served(client):
    resp = await client.get("/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


async def test_app_js_served(client):
    resp = await client.get("/app.js")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in (
        "text/javascript; charset=utf-8",
        "application/javascript",
        "application/javascript; charset=utf-8",
        "text/javascript",
    )


async def test_nonexistent_static_path_404s(client):
    resp = await client.get("/some-nonexistent-page")
    assert resp.status_code == 404
