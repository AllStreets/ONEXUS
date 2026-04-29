"""
API routes for multi-modal file processing.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from nexus.multimodal.processor import MultiModalProcessor
from nexus.multimodal.integration import MultiModalCortex

router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])


def _get_kernel(request: Request):
    return request.app.state.kernel


def _get_processor(request: Request) -> MultiModalProcessor:
    """Get or create a MultiModalProcessor from the app state."""
    if not hasattr(request.app.state, "multimodal_processor"):
        request.app.state.multimodal_processor = MultiModalProcessor()
    return request.app.state.multimodal_processor


# ── Response models ────────────────────────────────────────────────────────


class ProcessResponse(BaseModel):
    input_type: str
    text_content: str
    metadata: dict[str, Any]
    llm_enhanced: bool
    processing_time_ms: float


class FormatsResponse(BaseModel):
    formats: dict[str, list[str]]


class DescribeResponse(BaseModel):
    input_type: str
    text_content: str
    cortex_response: str
    processing_time_ms: float


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/process", response_model=ProcessResponse)
async def process_file(
    request: Request,
    file: UploadFile = File(...),
    input_type: str | None = Form(default=None),
) -> ProcessResponse:
    """Upload a file for multi-modal processing.

    Accepts any supported file format (image, audio, document).
    Returns extracted text content and metadata.
    """
    processor = _get_processor(request)

    # Determine extension from uploaded filename
    ext = ""
    if file.filename:
        ext = os.path.splitext(file.filename)[1]

    # Write to a temp file so processors can read it
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {exc}")

    try:
        result = await processor.process(tmp_path, input_type=input_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {exc}")
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return ProcessResponse(
        input_type=result.input_type,
        text_content=result.text_content,
        metadata=result.metadata,
        llm_enhanced=result.llm_enhanced,
        processing_time_ms=result.processing_time_ms,
    )


@router.get("/formats", response_model=FormatsResponse)
async def list_formats() -> FormatsResponse:
    """List all supported file formats grouped by type."""
    return FormatsResponse(formats=MultiModalProcessor.supported_formats())


@router.post("/describe", response_model=DescribeResponse)
async def describe_file(
    request: Request,
    file: UploadFile = File(...),
    instruction: str = Form(default=""),
) -> DescribeResponse:
    """Process a file and route the result through Cortex.

    Combines multimodal processing with Cortex message routing.
    For example, uploading a PDF with instruction "review this contract"
    will extract text and route it to the appropriate module.
    """
    processor = _get_processor(request)
    kernel = _get_kernel(request)

    ext = ""
    if file.filename:
        ext = os.path.splitext(file.filename)[1]

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {exc}")

    try:
        import time
        start = time.monotonic()

        bridge = MultiModalCortex(processor=processor, cortex=kernel.cortex)
        cortex_response = await bridge.process_and_route(tmp_path, instruction=instruction)

        # Also get the raw processed result for the response
        result = await processor.process(tmp_path)
        elapsed_ms = (time.monotonic() - start) * 1000

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return DescribeResponse(
        input_type=result.input_type,
        text_content=result.text_content,
        cortex_response=cortex_response,
        processing_time_ms=elapsed_ms,
    )
