"""Route/method-mismatch edge cases people commonly get wrong."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_get_single_book_falls_through_to_static_404(client):
    # /book/{book_id} is registered for PATCH/DELETE only. It's tempting to
    # assume GET on that path is a 405 (method mismatch), but the catch-all
    # StaticFiles mount at "/" is an unconditional full match in Starlette's
    # routing, which wins over the other routes' partial (path-only) matches
    # for the wrong method — so this actually 404s via StaticFiles, not 405.
    resp = await client.get("/book/some-id")
    assert resp.status_code == 404
