"""Aurora — the new visual surface. Serves /aurora and its static assets.

Classic /dashboard remains available (spec §13.4 backward-compat).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response


router = APIRouter(tags=["aurora"])
_STATIC_DIR = Path(__file__).parent.parent.parent / "aurora"


@router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    """Send the bare host (e.g. http://localhost:8765/) to the Aurora UI, so a
    bookmark to the server root lands on the app instead of a 404."""
    return RedirectResponse(url="/aurora")


# Aurora ships from disk on every request — there is no build step. To make
# sure browsers always pick up the latest CSS/JS while iterating, send
# Cache-Control: no-store. The cost is negligible (small files, local network).
_NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


@router.get("/aurora", response_class=HTMLResponse)
async def aurora_index():
    """Serve the Aurora shell. Asset URLs are versioned with mtime hashes so
    browsers (whose ESM loader caches by URL) always pick up fresh CSS/JS."""
    html = (_STATIC_DIR / "index.html").read_text()
    # Stamp each static asset URL with the file's mtime so any change to
    # app.js / app.css / icons.js invalidates the browser-side module cache.
    for asset in ("tokens.css", "mood.css", "app.css", "app.js", "icons.js"):
        path = _STATIC_DIR / asset
        if path.exists():
            v = int(path.stat().st_mtime)
            html = html.replace(f"/aurora/static/{asset}", f"/aurora/static/{asset}?v={v}")
    return HTMLResponse(content=html, headers=_NO_STORE)


@router.get("/aurora/static/{filename:path}")
async def aurora_static(filename: str):
    path = _STATIC_DIR / filename
    if not path.exists() or not path.is_file():
        return Response(status_code=404)
    media_type = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".html": "text/html",
        ".svg": "image/svg+xml",
    }.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type, headers=_NO_STORE)
