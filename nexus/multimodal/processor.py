"""
MultiModalProcessor -- main entry point for processing non-text inputs into text
representations that NEXUS modules can work with.
"""
from __future__ import annotations

import time
from pathlib import Path

from nexus.multimodal.models import ProcessedInput
from nexus.multimodal.image import ImageProcessor
from nexus.multimodal.audio import AudioProcessor
from nexus.multimodal.document import DocumentProcessor


# Extension-to-type mapping
_TYPE_MAP: dict[str, str] = {}
for ext in ImageProcessor.SUPPORTED_FORMATS:
    _TYPE_MAP[ext] = "image"
for ext in AudioProcessor.SUPPORTED_FORMATS:
    _TYPE_MAP[ext] = "audio"
for ext in DocumentProcessor.SUPPORTED_FORMATS:
    _TYPE_MAP[ext] = "document"


class MultiModalProcessor:
    """Processes non-text inputs into text representations for NEXUS modules."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.image_processor = ImageProcessor()
        self.audio_processor = AudioProcessor()
        self.document_processor = DocumentProcessor()

    async def process(self, input_path: str, input_type: str | None = None) -> ProcessedInput:
        """Process any supported input file into text.

        Auto-detects type from extension if not specified.
        Supported: images (png, jpg, gif, webp), audio (wav, mp3, ogg, flac),
                   documents (pdf, txt, csv, json)
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if input_type is None:
            input_type = self.detect_type(input_path)

        start = time.monotonic()

        if input_type == "image":
            result = await self.image_processor.process(input_path, self.llm_client)
            text = result.description
            if result.width and result.height:
                text = (
                    f"Image: {result.format.upper()} {result.width}x{result.height}\n"
                    f"File size: {result.file_size} bytes\n"
                    f"Description: {result.description}"
                )
            metadata = result.metadata
            llm_enhanced = result.llm_enhanced

        elif input_type == "audio":
            result = await self.audio_processor.process(input_path, self.llm_client)
            text = result.transcription
            if result.duration_seconds > 0:
                text = (
                    f"Audio: {result.format.upper()} {result.duration_seconds:.1f}s "
                    f"{result.sample_rate}Hz {result.channels}ch\n"
                    f"Transcription: {result.transcription}"
                )
            metadata = result.metadata
            llm_enhanced = result.llm_enhanced

        elif input_type == "document":
            result = await self.document_processor.process(input_path)
            text = result.text_content
            metadata = result.metadata
            metadata["word_count"] = result.word_count
            metadata["line_count"] = result.line_count
            llm_enhanced = False

        else:
            raise ValueError(f"Unknown input type: {input_type}")

        elapsed_ms = (time.monotonic() - start) * 1000

        return ProcessedInput(
            original_path=input_path,
            input_type=input_type,
            text_content=text,
            metadata=metadata,
            llm_enhanced=llm_enhanced,
            processing_time_ms=elapsed_ms,
        )

    def detect_type(self, path: str) -> str:
        """Detect input type from file extension."""
        ext = Path(path).suffix.lower()
        detected = _TYPE_MAP.get(ext)
        if detected is None:
            raise ValueError(
                f"Cannot detect type for extension '{ext}'. "
                f"Supported extensions: {sorted(_TYPE_MAP.keys())}"
            )
        return detected

    @staticmethod
    def supported_formats() -> dict[str, list[str]]:
        """Return a dict of type -> list of supported extensions."""
        result: dict[str, list[str]] = {"image": [], "audio": [], "document": []}
        for ext, typ in sorted(_TYPE_MAP.items()):
            result[typ].append(ext)
        return result
