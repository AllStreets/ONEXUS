from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(tags=["dashboard"])
DASHBOARD_DIR = Path(__file__).parent.parent.parent / "dashboard"


@router.get("/dashboard")
async def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")


@router.get("/dashboard/{path:path}")
async def dashboard_static(path: str):
    file_path = DASHBOARD_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(DASHBOARD_DIR / "index.html")
