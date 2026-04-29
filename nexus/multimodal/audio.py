"""
AudioProcessor -- extracts metadata from audio files and optionally transcribes via LLM.
Parses WAV RIFF headers directly with struct (no external deps).
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

from nexus.multimodal.models import AudioResult


class AudioProcessor:
    """Processes audio files into text transcriptions."""

    SUPPORTED_FORMATS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

    async def process(self, audio_path: str, llm_client=None) -> AudioResult:
        """Process an audio file.

        Without LLM: extracts metadata (duration, format, sample rate, channels).
        With LLM (speech model): transcribes audio.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {ext}")

        meta = self.extract_metadata(audio_path)
        transcription = "No speech model available"
        llm_enhanced = False

        if llm_client is not None:
            try:
                transcription = await self.transcribe_with_llm(audio_path, llm_client)
                llm_enhanced = True
            except Exception:
                pass

        return AudioResult(
            path=audio_path,
            duration_seconds=meta.get("duration_seconds", 0.0),
            sample_rate=meta.get("sample_rate", 0),
            channels=meta.get("channels", 0),
            format=meta.get("format", ext.lstrip(".")),
            file_size=meta.get("file_size", 0),
            transcription=transcription,
            metadata=meta,
            llm_enhanced=llm_enhanced,
        )

    def extract_metadata(self, audio_path: str) -> dict:
        """Extract audio metadata without external dependencies.

        Parses WAV headers directly; for other formats, returns file-level info.
        """
        path = Path(audio_path)
        file_size = path.stat().st_size
        ext = path.suffix.lower()

        meta: dict = {
            "file_size": file_size,
            "format": ext.lstrip("."),
        }

        if ext == ".wav":
            with open(audio_path, "rb") as f:
                data = f.read(min(file_size, 4096))
            meta.update(self.parse_wav_header(data))
        elif ext == ".flac":
            with open(audio_path, "rb") as f:
                data = f.read(min(file_size, 4096))
            meta.update(self._parse_flac_header(data))

        return meta

    def parse_wav_header(self, data: bytes) -> dict:
        """Parse WAV/RIFF header for audio properties.

        RIFF header layout:
        - 0-3:   "RIFF"
        - 4-7:   file size - 8
        - 8-11:  "WAVE"
        - 12-15: "fmt " sub-chunk id
        - 16-19: sub-chunk size
        - 20-21: audio format (1 = PCM)
        - 22-23: num channels
        - 24-27: sample rate
        - 28-31: byte rate
        - 32-33: block align
        - 34-35: bits per sample
        Then search for "data" sub-chunk for data size.
        """
        info: dict = {}
        if len(data) < 44:
            return info

        # Validate RIFF/WAVE header
        if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
            return info

        # Find fmt chunk
        offset = 12
        fmt_found = False
        while offset < len(data) - 8:
            chunk_id = data[offset:offset + 4]
            chunk_size = struct.unpack("<I", data[offset + 4:offset + 8])[0]

            if chunk_id == b"fmt ":
                if offset + 8 + chunk_size > len(data):
                    break
                fmt_data = data[offset + 8:offset + 8 + chunk_size]
                if len(fmt_data) >= 16:
                    audio_format = struct.unpack("<H", fmt_data[0:2])[0]
                    channels = struct.unpack("<H", fmt_data[2:4])[0]
                    sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                    byte_rate = struct.unpack("<I", fmt_data[8:12])[0]
                    block_align = struct.unpack("<H", fmt_data[12:14])[0]
                    bits_per_sample = struct.unpack("<H", fmt_data[14:16])[0]

                    info["audio_format"] = audio_format
                    info["channels"] = channels
                    info["sample_rate"] = sample_rate
                    info["byte_rate"] = byte_rate
                    info["block_align"] = block_align
                    info["bits_per_sample"] = bits_per_sample
                    fmt_found = True

                offset += 8 + chunk_size
                continue

            if chunk_id == b"data":
                data_size = chunk_size
                info["data_size"] = data_size

                # Calculate duration if we have fmt info
                if fmt_found and info.get("byte_rate", 0) > 0:
                    info["duration_seconds"] = data_size / info["byte_rate"]

                break

            offset += 8 + chunk_size

        return info

    def _parse_flac_header(self, data: bytes) -> dict:
        """Parse FLAC stream info block for basic metadata."""
        info: dict = {}
        if len(data) < 42:
            return info
        if data[0:4] != b"fLaC":
            return info

        # STREAMINFO is always the first metadata block
        # Block header: 1 byte (type + last flag), 3 bytes (length)
        block_type = data[4] & 0x7F
        if block_type != 0:  # 0 = STREAMINFO
            return info

        block_length = struct.unpack(">I", b"\x00" + data[5:8])[0]
        if len(data) < 8 + block_length or block_length < 34:
            return info

        si = data[8:8 + block_length]

        # STREAMINFO layout (big-endian):
        # 0-1: min block size, 2-3: max block size
        # 4-6: min frame size (24 bits), 7-9: max frame size (24 bits)
        # 10-13: sample rate (20 bits) | channels (3 bits) | bps (5 bits) | total samples high (4 bits)
        # 14-17: total samples low (32 bits)

        sr_chan_bps = struct.unpack(">I", si[10:14])[0]
        sample_rate = (sr_chan_bps >> 12) & 0xFFFFF
        channels = ((sr_chan_bps >> 9) & 0x7) + 1
        bits_per_sample = ((sr_chan_bps >> 4) & 0x1F) + 1
        total_samples_high = sr_chan_bps & 0xF
        total_samples_low = struct.unpack(">I", si[14:18])[0]
        total_samples = (total_samples_high << 32) | total_samples_low

        info["sample_rate"] = sample_rate
        info["channels"] = channels
        info["bits_per_sample"] = bits_per_sample
        info["total_samples"] = total_samples
        if sample_rate > 0:
            info["duration_seconds"] = total_samples / sample_rate

        return info

    async def transcribe_with_llm(self, audio_path: str, llm_client) -> str:
        """Transcribe audio using speech-capable LLM.

        This is a placeholder integration point. Real transcription would require
        a speech-to-text model (Whisper, etc.) or an API that accepts audio.
        """
        import base64

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        encoded = base64.b64encode(audio_data).decode("utf-8")

        response = await llm_client.chat(
            system="You are an audio transcription assistant.",
            user=f"[Audio data: base64 encoded, {len(audio_data)} bytes]\nPlease transcribe this audio.",
        )
        return response
