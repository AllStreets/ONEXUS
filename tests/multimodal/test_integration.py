"""Tests for MultiModalCortex integration -- routing processed files through Cortex."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.multimodal.integration import MultiModalCortex
from nexus.multimodal.processor import MultiModalProcessor
from nexus.multimodal.models import ProcessedInput


class TestMultiModalCortex:
    @pytest.mark.asyncio
    async def test_process_and_route_text_document(self, tmp_path):
        # Create a test document
        txt_file = tmp_path / "contract.txt"
        txt_file.write_text("This is a test contract with terms and conditions.")

        # Create a real processor (document processing needs no LLM)
        processor = MultiModalProcessor()

        # Mock Cortex
        mock_cortex = MagicMock()
        mock_cortex.process = AsyncMock(return_value="Contract reviewed: looks good.")

        bridge = MultiModalCortex(processor=processor, cortex=mock_cortex)
        response = await bridge.process_and_route(str(txt_file), instruction="review this contract")

        assert response == "Contract reviewed: looks good."
        mock_cortex.process.assert_called_once()

        # Verify the message passed to Cortex contains both instruction and content
        call_args = mock_cortex.process.call_args[0][0]
        assert "review this contract" in call_args
        assert "test contract" in call_args

    @pytest.mark.asyncio
    async def test_process_and_route_without_instruction(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Meeting notes from today.")

        processor = MultiModalProcessor()

        mock_cortex = MagicMock()
        mock_cortex.process = AsyncMock(return_value="Notes processed.")

        bridge = MultiModalCortex(processor=processor, cortex=mock_cortex)
        response = await bridge.process_and_route(str(txt_file))

        assert response == "Notes processed."
        call_args = mock_cortex.process.call_args[0][0]
        assert "Meeting notes from today" in call_args

    @pytest.mark.asyncio
    async def test_process_and_route_csv(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,score\nAlice,95\nBob,87\n")

        processor = MultiModalProcessor()

        mock_cortex = MagicMock()
        mock_cortex.process = AsyncMock(return_value="Data analyzed.")

        bridge = MultiModalCortex(processor=processor, cortex=mock_cortex)
        response = await bridge.process_and_route(str(csv_file), instruction="analyze this data")

        assert response == "Data analyzed."
        call_args = mock_cortex.process.call_args[0][0]
        assert "analyze this data" in call_args
        assert "Alice" in call_args

    @pytest.mark.asyncio
    async def test_process_and_route_includes_metadata(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Some content.")

        processor = MultiModalProcessor()

        mock_cortex = MagicMock()
        mock_cortex.process = AsyncMock(return_value="OK")

        bridge = MultiModalCortex(processor=processor, cortex=mock_cortex)
        await bridge.process_and_route(str(txt_file))

        call_args = mock_cortex.process.call_args[0][0]
        assert "Metadata" in call_args

    @pytest.mark.asyncio
    async def test_process_and_route_file_not_found(self):
        processor = MultiModalProcessor()
        mock_cortex = MagicMock()

        bridge = MultiModalCortex(processor=processor, cortex=mock_cortex)
        with pytest.raises(FileNotFoundError):
            await bridge.process_and_route("/nonexistent/file.txt")
