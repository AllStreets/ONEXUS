"""
nexus.multimodal -- processing pipelines for images, audio, and documents.
Converts non-text inputs into text representations that NEXUS modules can consume.
"""
from __future__ import annotations

from nexus.multimodal.models import (
    AudioResult,
    DocumentResult,
    ImageResult,
    ProcessedInput,
)
from nexus.multimodal.processor import MultiModalProcessor
from nexus.multimodal.image import ImageProcessor
from nexus.multimodal.audio import AudioProcessor
from nexus.multimodal.document import DocumentProcessor
from nexus.multimodal.integration import MultiModalCortex

__all__ = [
    "MultiModalProcessor",
    "ImageProcessor",
    "AudioProcessor",
    "DocumentProcessor",
    "MultiModalCortex",
    "ProcessedInput",
    "ImageResult",
    "AudioResult",
    "DocumentResult",
]
