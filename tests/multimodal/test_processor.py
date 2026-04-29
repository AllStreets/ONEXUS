"""Tests for the main MultiModalProcessor -- auto-detection and processing pipeline."""
from __future__ import annotations

import struct

import pytest

from nexus.multimodal.processor import MultiModalProcessor


def _make_minimal_png(width: int = 100, height: int = 80) -> bytes:
    """Minimal PNG for testing."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", 0)
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0)
    return signature + ihdr_chunk + iend_chunk


def _make_minimal_wav(sample_rate: int = 44100, channels: int = 2, num_samples: int = 44100) -> bytes:
    """Minimal WAV for testing."""
    bits_per_sample = 16
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = num_samples * channels * (bits_per_sample // 8)

    fmt_chunk = b"fmt " + struct.pack("<I", 16)
    fmt_chunk += struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits_per_sample)

    data_chunk = b"data" + struct.pack("<I", data_size) + b"\x00" * min(data_size, 256)

    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + fmt_chunk + data_chunk


@pytest.fixture
def processor():
    return MultiModalProcessor()


class TestTypeDetection:
    def test_detect_png(self, processor):
        assert processor.detect_type("photo.png") == "image"

    def test_detect_jpg(self, processor):
        assert processor.detect_type("photo.jpg") == "image"

    def test_detect_jpeg(self, processor):
        assert processor.detect_type("photo.jpeg") == "image"

    def test_detect_gif(self, processor):
        assert processor.detect_type("anim.gif") == "image"

    def test_detect_webp(self, processor):
        assert processor.detect_type("photo.webp") == "image"

    def test_detect_wav(self, processor):
        assert processor.detect_type("recording.wav") == "audio"

    def test_detect_mp3(self, processor):
        assert processor.detect_type("song.mp3") == "audio"

    def test_detect_ogg(self, processor):
        assert processor.detect_type("audio.ogg") == "audio"

    def test_detect_flac(self, processor):
        assert processor.detect_type("music.flac") == "audio"

    def test_detect_txt(self, processor):
        assert processor.detect_type("readme.txt") == "document"

    def test_detect_csv(self, processor):
        assert processor.detect_type("data.csv") == "document"

    def test_detect_json(self, processor):
        assert processor.detect_type("config.json") == "document"

    def test_detect_pdf(self, processor):
        assert processor.detect_type("report.pdf") == "document"

    def test_detect_html(self, processor):
        assert processor.detect_type("page.html") == "document"

    def test_detect_yaml(self, processor):
        assert processor.detect_type("config.yaml") == "document"

    def test_detect_yml(self, processor):
        assert processor.detect_type("config.yml") == "document"

    def test_detect_md(self, processor):
        assert processor.detect_type("README.md") == "document"

    def test_detect_unknown_raises(self, processor):
        with pytest.raises(ValueError, match="Cannot detect type"):
            processor.detect_type("file.xyz")


class TestProcessPipeline:
    @pytest.mark.asyncio
    async def test_process_image(self, processor, tmp_path):
        png_data = _make_minimal_png(width=320, height=240)
        png_file = tmp_path / "test.png"
        png_file.write_bytes(png_data)

        result = await processor.process(str(png_file))
        assert result.input_type == "image"
        assert result.original_path == str(png_file)
        assert "320x240" in result.text_content
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_audio(self, processor, tmp_path):
        wav_data = _make_minimal_wav()
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(wav_data)

        result = await processor.process(str(wav_file))
        assert result.input_type == "audio"
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_document(self, processor, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello from NEXUS multimodal processor.")

        result = await processor.process(str(txt_file))
        assert result.input_type == "document"
        assert "Hello from NEXUS" in result.text_content
        assert result.llm_enhanced is False

    @pytest.mark.asyncio
    async def test_process_with_explicit_type(self, processor, tmp_path):
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some text")

        result = await processor.process(str(txt_file), input_type="document")
        assert result.input_type == "document"

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, processor):
        with pytest.raises(FileNotFoundError):
            await processor.process("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_process_unknown_type(self, processor, tmp_path):
        bad_file = tmp_path / "file.zzz"
        bad_file.write_text("data")
        with pytest.raises(ValueError):
            await processor.process(str(bad_file))


class TestSupportedFormats:
    def test_supported_formats_dict(self):
        formats = MultiModalProcessor.supported_formats()
        assert "image" in formats
        assert "audio" in formats
        assert "document" in formats
        assert ".png" in formats["image"]
        assert ".wav" in formats["audio"]
        assert ".txt" in formats["document"]
