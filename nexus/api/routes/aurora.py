"""Aurora — the new visual surface. Serves /aurora and its static assets.

Classic /dashboard remains available (spec §13.4 backward-compat).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response


router = APIRouter(tags=["aurora"])
_STATIC_DIR = Path(__file__).parent.parent.parent / "aurora"


@router.get("/aurora", response_class=HTMLResponse)
async def aurora_index():
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


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
    return FileResponse(path, media_type=media_type)
