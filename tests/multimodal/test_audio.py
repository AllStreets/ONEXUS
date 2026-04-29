"""Tests for audio processing -- WAV header parsing and metadata extraction."""
from __future__ import annotations

import struct

import pytest

from nexus.multimodal.audio import AudioProcessor


def _make_minimal_wav(
    sample_rate: int = 44100,
    channels: int = 2,
    bits_per_sample: int = 16,
    num_samples: int = 44100,  # 1 second of audio
) -> bytes:
    """Create a minimal valid WAV file with RIFF/WAVE header."""
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = num_samples * channels * (bits_per_sample // 8)

    # fmt chunk
    fmt_chunk = b"fmt "
    fmt_chunk += struct.pack("<I", 16)           # chunk size
    fmt_chunk += struct.pack("<H", 1)            # PCM format
    fmt_chunk += struct.pack("<H", channels)
    fmt_chunk += struct.pack("<I", sample_rate)
    fmt_chunk += struct.pack("<I", byte_rate)
    fmt_chunk += struct.pack("<H", block_align)
    fmt_chunk += struct.pack("<H", bits_per_sample)

    # data chunk (header only, no actual audio data needed for header parsing)
    data_chunk = b"data"
    data_chunk += struct.pack("<I", data_size)
    # Add a few bytes of silence
    data_chunk += b"\x00" * min(data_size, 1024)

    # RIFF header
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    riff = b"RIFF"
    riff += struct.pack("<I", riff_size)
    riff += b"WAVE"

    return riff + fmt_chunk + data_chunk


def _make_minimal_flac(
    sample_rate: int = 48000,
    channels: int = 2,
    bits_per_sample: int = 24,
    total_samples: int = 96000,
) -> bytes:
    """Create minimal FLAC with a STREAMINFO metadata block."""
    marker = b"fLaC"

    # STREAMINFO block (34 bytes)
    # block header: type=0 (STREAMINFO), last=1 -> 0x80, length=34
    block_header = struct.pack(">B", 0x80)  # last block, type 0
    block_header += struct.pack(">I", 34)[1:]  # 3-byte length = 34

    # STREAMINFO data
    min_block = 4096
    max_block = 4096
    min_frame = 0
    max_frame = 0

    si = struct.pack(">HH", min_block, max_block)
    si += struct.pack(">I", min_frame)[1:]  # 3 bytes
    si += struct.pack(">I", max_frame)[1:]  # 3 bytes

    # sample_rate(20) | channels-1(3) | bps-1(5) | total_samples_high(4)
    total_high = (total_samples >> 32) & 0xF
    sr_chan_bps = (sample_rate << 12) | ((channels - 1) << 9) | ((bits_per_sample - 1) << 4) | total_high
    si += struct.pack(">I", sr_chan_bps)
    si += struct.pack(">I", total_samples & 0xFFFFFFFF)

    # MD5 signature (16 bytes of zeros)
    si += b"\x00" * 16

    return marker + block_header + si


@pytest.fixture
def audio_processor():
    return AudioProcessor()


class TestWAVParsing:
    def test_parse_wav_sample_rate(self, audio_processor):
        data = _make_minimal_wav(sample_rate=44100)
        info = audio_processor.parse_wav_header(data)
        assert info["sample_rate"] == 44100

    def test_parse_wav_channels(self, audio_processor):
        data = _make_minimal_wav(channels=2)
        info = audio_processor.parse_wav_header(data)
        assert info["channels"] == 2

    def test_parse_wav_mono(self, audio_processor):
        data = _make_minimal_wav(channels=1)
        info = audio_processor.parse_wav_header(data)
        assert info["channels"] == 1

    def test_parse_wav_bits_per_sample(self, audio_processor):
        data = _make_minimal_wav(bits_per_sample=24)
        info = audio_processor.parse_wav_header(data)
        assert info["bits_per_sample"] == 24

    def test_parse_wav_duration(self, audio_processor):
        # 1 second of stereo 16-bit audio at 44100 Hz
        data = _make_minimal_wav(sample_rate=44100, channels=2, bits_per_sample=16, num_samples=44100)
        info = audio_processor.parse_wav_header(data)
        assert abs(info["duration_seconds"] - 1.0) < 0.01

    def test_parse_wav_pcm_format(self, audio_processor):
        data = _make_minimal_wav()
        info = audio_processor.parse_wav_header(data)
        assert info["audio_format"] == 1  # PCM

    def test_invalid_wav(self, audio_processor):
        info = audio_processor.parse_wav_header(b"not a wav file")
        assert info == {}

    def test_truncated_wav(self, audio_processor):
        info = audio_processor.parse_wav_header(b"RIFF\x00\x00\x00\x00WAVE")
        assert info == {}

    def test_parse_wav_48khz(self, audio_processor):
        data = _make_minimal_wav(sample_rate=48000)
        info = audio_processor.parse_wav_header(data)
        assert info["sample_rate"] == 48000


class TestFLACParsing:
    def test_parse_flac_sample_rate(self, audio_processor):
        data = _make_minimal_flac(sample_rate=48000)
        info = audio_processor._parse_flac_header(data)
        assert info["sample_rate"] == 48000

    def test_parse_flac_channels(self, audio_processor):
        data = _make_minimal_flac(channels=2)
        info = audio_processor._parse_flac_header(data)
        assert info["channels"] == 2

    def test_parse_flac_bits(self, audio_processor):
        data = _make_minimal_flac(bits_per_sample=24)
        info = audio_processor._parse_flac_header(data)
        assert info["bits_per_sample"] == 24

    def test_parse_flac_duration(self, audio_processor):
        data = _make_minimal_flac(sample_rate=48000, total_samples=96000)
        info = audio_processor._parse_flac_header(data)
        assert abs(info["duration_seconds"] - 2.0) < 0.01

    def test_invalid_flac(self, audio_processor):
        info = audio_processor._parse_flac_header(b"not flac")
        assert info == {}


class TestMetadataExtraction:
    def test_wav_metadata_from_file(self, audio_processor, tmp_path):
        wav_data = _make_minimal_wav(sample_rate=22050, channels=1, bits_per_sample=16, num_samples=22050)
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(wav_data)

        meta = audio_processor.extract_metadata(str(wav_file))
        assert meta["sample_rate"] == 22050
        assert meta["channels"] == 1
        assert meta["format"] == "wav"
        assert meta["file_size"] > 0

    def test_flac_metadata_from_file(self, audio_processor, tmp_path):
        flac_data = _make_minimal_flac(sample_rate=44100, channels=2)
        flac_file = tmp_path / "test.flac"
        flac_file.write_bytes(flac_data)

        meta = audio_processor.extract_metadata(str(flac_file))
        assert meta["sample_rate"] == 44100
        assert meta["channels"] == 2

    def test_unsupported_format_basic_meta(self, audio_processor, tmp_path):
        mp3_file = tmp_path / "test.mp3"
        mp3_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)

        meta = audio_processor.extract_metadata(str(mp3_file))
        assert meta["format"] == "mp3"
        assert meta["file_size"] > 0


class TestAudioProcess:
    @pytest.mark.asyncio
    async def test_process_without_llm(self, audio_processor, tmp_path):
        wav_data = _make_minimal_wav(sample_rate=44100, channels=2, num_samples=88200)
        wav_file = tmp_path / "audio.wav"
        wav_file.write_bytes(wav_data)

        result = await audio_processor.process(str(wav_file))
        assert result.sample_rate == 44100
        assert result.channels == 2
        assert result.format == "wav"
        assert result.transcription == "No speech model available"
        assert result.llm_enhanced is False

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, audio_processor):
        with pytest.raises(FileNotFoundError):
            await audio_processor.process("/nonexistent/audio.wav")

    @pytest.mark.asyncio
    async def test_process_unsupported_format(self, audio_processor, tmp_path):
        bad_file = tmp_path / "test.aac"
        bad_file.write_text("data")
        with pytest.raises(ValueError, match="Unsupported audio format"):
            await audio_processor.process(str(bad_file))

    def test_supported_formats(self, audio_processor):
        assert ".wav" in audio_processor.SUPPORTED_FORMATS
        assert ".mp3" in audio_processor.SUPPORTED_FORMATS
        assert ".ogg" in audio_processor.SUPPORTED_FORMATS
        assert ".flac" in audio_processor.SUPPORTED_FORMATS
        assert ".m4a" in audio_processor.SUPPORTED_FORMATS
