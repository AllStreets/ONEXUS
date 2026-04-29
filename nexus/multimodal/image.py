"""
ImageProcessor -- extracts metadata from images and optionally describes them via LLM.
Parses PNG IHDR and JPEG SOF headers directly with struct (no external deps).
"""
from __future__ import annotations

import base64
import os
import struct
from pathlib import Path

from nexus.multimodal.models import ImageResult


class ImageProcessor:
    """Processes images into text descriptions."""

    SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}

    async def process(self, image_path: str, llm_client=None) -> ImageResult:
        """Process an image file.

        Without LLM: extracts metadata (size, format, dimensions).
        With LLM (vision model): generates image description.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {ext}")

        meta = self.extract_metadata(image_path)
        description = "No vision model available"
        llm_enhanced = False

        if llm_client is not None:
            try:
                description = await self.describe_with_llm(image_path, llm_client)
                llm_enhanced = True
            except Exception:
                pass

        return ImageResult(
            path=image_path,
            width=meta.get("width", 0),
            height=meta.get("height", 0),
            format=meta.get("format", ext.lstrip(".")),
            file_size=meta.get("file_size", 0),
            description=description,
            metadata=meta,
            llm_enhanced=llm_enhanced,
        )

    def extract_metadata(self, image_path: str) -> dict:
        """Extract image metadata without any external dependencies.

        Uses struct to parse PNG/JPEG headers directly.
        """
        path = Path(image_path)
        file_size = path.stat().st_size
        ext = path.suffix.lower()

        with open(image_path, "rb") as f:
            data = f.read(min(file_size, 65536))  # read up to 64KB for headers

        meta: dict = {
            "file_size": file_size,
            "format": ext.lstrip("."),
        }

        if ext == ".png":
            meta.update(self.extract_png_info(data))
        elif ext in {".jpg", ".jpeg"}:
            meta.update(self.extract_jpeg_info(data))
        elif ext == ".gif":
            meta.update(self._extract_gif_info(data))
        elif ext == ".bmp":
            meta.update(self._extract_bmp_info(data))

        return meta

    def extract_png_info(self, data: bytes) -> dict:
        """Parse PNG IHDR chunk for dimensions and color info."""
        info: dict = {}
        # PNG signature: 8 bytes
        if len(data) < 24:
            return info
        sig = data[:8]
        if sig != b"\x89PNG\r\n\x1a\n":
            return info

        # IHDR is always the first chunk after the 8-byte signature
        # Chunk layout: 4 bytes length, 4 bytes type, then data
        chunk_length = struct.unpack(">I", data[8:12])[0]
        chunk_type = data[12:16]
        if chunk_type != b"IHDR" or chunk_length < 13:
            return info

        # IHDR data: width(4), height(4), bit_depth(1), color_type(1),
        #            compression(1), filter(1), interlace(1)
        width, height = struct.unpack(">II", data[16:24])
        bit_depth = data[24]
        color_type = data[25]

        color_type_names = {
            0: "grayscale",
            2: "rgb",
            3: "indexed",
            4: "grayscale_alpha",
            6: "rgba",
        }

        info["width"] = width
        info["height"] = height
        info["bit_depth"] = bit_depth
        info["color_type"] = color_type_names.get(color_type, f"unknown({color_type})")
        return info

    def extract_jpeg_info(self, data: bytes) -> dict:
        """Parse JPEG SOF marker for dimensions."""
        info: dict = {}
        if len(data) < 2 or data[0:2] != b"\xff\xd8":
            return info

        offset = 2
        while offset < len(data) - 1:
            if data[offset] != 0xFF:
                offset += 1
                continue

            marker = data[offset + 1]

            # SOF markers: 0xC0-0xC3, 0xC5-0xC7, 0xC9-0xCB, 0xCD-0xCF
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if offset + 9 >= len(data):
                    break
                # SOF layout: length(2), precision(1), height(2), width(2), components(1)
                precision = data[offset + 4]
                height = struct.unpack(">H", data[offset + 5:offset + 7])[0]
                width = struct.unpack(">H", data[offset + 7:offset + 9])[0]
                num_components = data[offset + 9] if offset + 9 < len(data) else 0

                info["width"] = width
                info["height"] = height
                info["bit_depth"] = precision
                info["num_components"] = num_components
                return info

            # Skip non-SOF markers
            if offset + 3 >= len(data):
                break
            seg_length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            offset += 2 + seg_length

        return info

    def _extract_gif_info(self, data: bytes) -> dict:
        """Parse GIF header for dimensions."""
        info: dict = {}
        if len(data) < 10:
            return info
        if data[:3] != b"GIF":
            return info
        width, height = struct.unpack("<HH", data[6:10])
        info["width"] = width
        info["height"] = height
        return info

    def _extract_bmp_info(self, data: bytes) -> dict:
        """Parse BMP header for dimensions."""
        info: dict = {}
        if len(data) < 26:
            return info
        if data[:2] != b"BM":
            return info
        width, height = struct.unpack("<ii", data[18:26])
        info["width"] = width
        info["height"] = abs(height)  # height can be negative (top-down)
        return info

    async def describe_with_llm(self, image_path: str, llm_client) -> str:
        """Generate image description using a vision-capable LLM."""
        with open(image_path, "rb") as f:
            image_data = f.read()

        encoded = base64.b64encode(image_data).decode("utf-8")

        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
        }
        mime_type = mime_map.get(ext, "image/png")

        prompt = (
            "Describe this image in detail. Include the main subject, "
            "colors, composition, and any text visible in the image."
        )

        # Try using the LLM client's chat method with a vision message
        response = await llm_client.chat(
            system="You are a precise image analysis assistant. Describe images accurately and concisely.",
            user=f"[Image: {mime_type};base64,{encoded}]\n\n{prompt}",
        )
        return response
