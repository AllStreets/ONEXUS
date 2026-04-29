"""
Data models for multi-modal processing results.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessedInput:
    """Unified result from any multi-modal processing pipeline."""
    original_path: str
    input_type: str          # "image", "audio", "document"
    text_content: str        # extracted/transcribed text
    metadata: dict = field(default_factory=dict)
    llm_enhanced: bool = False
    processing_time_ms: float = 0.0


@dataclass
class ImageResult:
    """Result from image processing."""
    path: str
    width: int = 0
    height: int = 0
    format: str = ""
    file_size: int = 0
    description: str = "No vision model available"
    metadata: dict = field(default_factory=dict)
    llm_enhanced: bool = False


@dataclass
class AudioResult:
    """Result from audio processing."""
    path: str
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    format: str = ""
    file_size: int = 0
    transcription: str = "No speech model available"
    metadata: dict = field(default_factory=dict)
    llm_enhanced: bool = False


@dataclass
class DocumentResult:
    """Result from document processing."""
    path: str
    format: str = ""
    file_size: int = 0
    text_content: str = ""
    word_count: int = 0
    line_count: int = 0
    metadata: dict = field(default_factory=dict)
