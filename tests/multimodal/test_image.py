"""Tests for image processing -- PNG/JPEG header parsing and metadata extraction."""
from __future__ import annotations

import os
import struct
import tempfile

import pytest

from nexus.multimodal.image import ImageProcessor


# ── Minimal valid file headers as byte strings ─────────────────────────────


def _make_minimal_png(width: int = 100, height: int = 80, bit_depth: int = 8, color_type: int = 6) -> bytes:
    """Create a minimal valid PNG file (signature + IHDR + IEND)."""
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    ihdr_crc = 0  # CRC not validated by our parser
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    # IEND chunk
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0)

    return signature + ihdr_chunk + iend_chunk


def _make_minimal_jpeg(width: int = 640, height: int = 480) -> bytes:
    """Create a minimal valid JPEG with SOI + SOF0 marker."""
    soi = b"\xff\xd8"

    # SOF0 marker (baseline DCT)
    # marker(2) + length(2) + precision(1) + height(2) + width(2) + num_components(1) + component_data
    num_components = 3
    component_data = b"\x01\x11\x00" * num_components  # Y, Cb, Cr
    sof_length = 8 + 3 * num_components
    sof = b"\xff\xc0" + struct.pack(">H", sof_length)
    sof += struct.pack(">B", 8)  # precision
    sof += struct.pack(">HH", height, width)
    sof += struct.pack(">B", num_components)
    sof += component_data

    eoi = b"\xff\xd9"
    return soi + sof + eoi


def _make_minimal_gif(width: int = 320, height: int = 240) -> bytes:
    """Create a minimal GIF header."""
    header = b"GIF89a"
    header += struct.pack("<HH", width, height)
    header += b"\x00\x00\x00"  # flags, background, aspect ratio
    return header


def _make_minimal_bmp(width: int = 200, height: int = 150) -> bytes:
    """Create a minimal BMP header."""
    header = b"BM"
    header += struct.pack("<I", 54)  # file size (header only)
    header += b"\x00\x00\x00\x00"    # reserved
    header += struct.pack("<I", 54)  # data offset
    header += struct.pack("<I", 40)  # DIB header size
    header += struct.pack("<ii", width, height)  # width, height (signed)
    return header


@pytest.fixture
def image_processor():
    return ImageProcessor()


class TestPNGParsing:
    def test_extract_png_dimensions(self, image_processor):
        data = _make_minimal_png(width=1920, height=1080)
        info = image_processor.extract_png_info(data)
        assert info["width"] == 1920
        assert info["height"] == 1080

    def test_extract_png_color_type_rgba(self, image_processor):
        data = _make_minimal_png(color_type=6)
        info = image_processor.extract_png_info(data)
        assert info["color_type"] == "rgba"

    def test_extract_png_color_type_rgb(self, image_processor):
        data = _make_minimal_png(color_type=2)
        info = image_processor.extract_png_info(data)
        assert info["color_type"] == "rgb"

    def test_extract_png_color_type_grayscale(self, image_processor):
        data = _make_minimal_png(color_type=0)
        info = image_processor.extract_png_info(data)
        assert info["color_type"] == "grayscale"

    def test_extract_png_bit_depth(self, image_processor):
        data = _make_minimal_png(bit_depth=16)
        info = image_processor.extract_png_info(data)
        assert info["bit_depth"] == 16

    def test_invalid_png_signature(self, image_processor):
        info = image_processor.extract_png_info(b"not a png file at all")
        assert info == {}

    def test_truncated_png(self, image_processor):
        info = image_processor.extract_png_info(b"\x89PNG\r\n\x1a\n\x00")
        assert info == {}


class TestJPEGParsing:
    def test_extract_jpeg_dimensions(self, image_processor):
        data = _make_minimal_jpeg(width=1280, height=720)
        info = image_processor.extract_jpeg_info(data)
        assert info["width"] == 1280
        assert info["height"] == 720

    def test_extract_jpeg_precision(self, image_processor):
        data = _make_minimal_jpeg()
        info = image_processor.extract_jpeg_info(data)
        assert info["bit_depth"] == 8

    def test_extract_jpeg_components(self, image_processor):
        data = _make_minimal_jpeg()
        info = image_processor.extract_jpeg_info(data)
        assert info["num_components"] == 3

    def test_invalid_jpeg(self, image_processor):
        info = image_processor.extract_jpeg_info(b"not a jpeg")
        assert info == {}


class TestGIFParsing:
    def test_extract_gif_dimensions(self, image_processor):
        data = _make_minimal_gif(width=320, height=240)
        info = image_processor._extract_gif_info(data)
        assert info["width"] == 320
        assert info["height"] == 240

    def test_invalid_gif(self, image_processor):
        info = image_processor._extract_gif_info(b"nope")
        assert info == {}


class TestBMPParsing:
    def test_extract_bmp_dimensions(self, image_processor):
        data = _make_minimal_bmp(width=200, height=150)
        info = image_processor._extract_bmp_info(data)
        assert info["width"] == 200
        assert info["height"] == 150

    def test_invalid_bmp(self, image_processor):
        info = image_processor._extract_bmp_info(b"XX")
        assert info == {}


class TestMetadataExtraction:
    def test_png_metadata_from_file(self, image_processor, tmp_path):
        png_data = _make_minimal_png(width=256, height=128)
        png_file = tmp_path / "test.png"
        png_file.write_bytes(png_data)

        meta = image_processor.extract_metadata(str(png_file))
        assert meta["width"] == 256
        assert meta["height"] == 128
        assert meta["format"] == "png"
        assert meta["file_size"] == len(png_data)

    def test_jpeg_metadata_from_file(self, image_processor, tmp_path):
        jpeg_data = _make_minimal_jpeg(width=800, height=600)
        jpeg_file = tmp_path / "test.jpg"
        jpeg_file.write_bytes(jpeg_data)

        meta = image_processor.extract_metadata(str(jpeg_file))
        assert meta["width"] == 800
        assert meta["height"] == 600
        assert meta["format"] == "jpg"


class TestImageProcess:
    @pytest.mark.asyncio
    async def test_process_without_llm(self, image_processor, tmp_path):
        png_data = _make_minimal_png(width=512, height=384)
        png_file = tmp_path / "photo.png"
        png_file.write_bytes(png_data)

        result = await image_processor.process(str(png_file))
        assert result.width == 512
        assert result.height == 384
        assert result.format == "png"
        assert result.description == "No vision model available"
        assert result.llm_enhanced is False

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, image_processor):
        with pytest.raises(FileNotFoundError):
            await image_processor.process("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_process_unsupported_format(self, image_processor, tmp_path):
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("data")
        with pytest.raises(ValueError, match="Unsupported image format"):
            await image_processor.process(str(bad_file))

    def test_supported_formats(self, image_processor):
        assert ".png" in image_processor.SUPPORTED_FORMATS
        assert ".jpg" in image_processor.SUPPORTED_FORMATS
        assert ".jpeg" in image_processor.SUPPORTED_FORMATS
        assert ".gif" in image_processor.SUPPORTED_FORMATS
        assert ".webp" in image_processor.SUPPORTED_FORMATS
