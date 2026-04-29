"""Tests for multimodal data models."""
from __future__ import annotations

from nexus.multimodal.models import (
    AudioResult,
    DocumentResult,
    ImageResult,
    ProcessedInput,
)


class TestProcessedInput:
    def test_defaults(self):
        pi = ProcessedInput(
            original_path="/tmp/test.png",
            input_type="image",
            text_content="a photo",
        )
        assert pi.original_path == "/tmp/test.png"
        assert pi.input_type == "image"
        assert pi.text_content == "a photo"
        assert pi.metadata == {}
        assert pi.llm_enhanced is False
        assert pi.processing_time_ms == 0.0

    def test_with_all_fields(self):
        pi = ProcessedInput(
            original_path="/data/file.wav",
            input_type="audio",
            text_content="transcription here",
            metadata={"sample_rate": 44100},
            llm_enhanced=True,
            processing_time_ms=123.4,
        )
        assert pi.llm_enhanced is True
        assert pi.metadata["sample_rate"] == 44100
        assert pi.processing_time_ms == 123.4


class TestImageResult:
    def test_defaults(self):
        ir = ImageResult(path="/tmp/img.png")
        assert ir.width == 0
        assert ir.height == 0
        assert ir.format == ""
        assert ir.description == "No vision model available"
        assert ir.llm_enhanced is False

    def test_with_values(self):
        ir = ImageResult(
            path="/tmp/img.jpg",
            width=1920,
            height=1080,
            format="jpeg",
            file_size=500000,
            description="A sunset over the ocean",
            llm_enhanced=True,
        )
        assert ir.width == 1920
        assert ir.height == 1080
        assert ir.description == "A sunset over the ocean"


class TestAudioResult:
    def test_defaults(self):
        ar = AudioResult(path="/tmp/audio.wav")
        assert ar.duration_seconds == 0.0
        assert ar.sample_rate == 0
        assert ar.channels == 0
        assert ar.transcription == "No speech model available"
        assert ar.llm_enhanced is False

    def test_with_values(self):
        ar = AudioResult(
            path="/tmp/audio.wav",
            duration_seconds=5.5,
            sample_rate=44100,
            channels=2,
            format="wav",
            file_size=484000,
            transcription="Hello world",
            llm_enhanced=True,
        )
        assert ar.duration_seconds == 5.5
        assert ar.channels == 2
        assert ar.transcription == "Hello world"


class TestDocumentResult:
    def test_defaults(self):
        dr = DocumentResult(path="/tmp/doc.txt")
        assert dr.format == ""
        assert dr.text_content == ""
        assert dr.word_count == 0
        assert dr.line_count == 0

    def test_with_values(self):
        dr = DocumentResult(
            path="/tmp/doc.csv",
            format="csv",
            file_size=2048,
            text_content="header1,header2\nval1,val2",
            word_count=4,
            line_count=2,
        )
        assert dr.format == "csv"
        assert dr.word_count == 4
