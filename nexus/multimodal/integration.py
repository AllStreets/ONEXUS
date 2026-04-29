"""
MultiModalCortex -- bridges multimodal processing with Cortex message routing.
"""
from __future__ import annotations

from nexus.multimodal.processor import MultiModalProcessor


class MultiModalCortex:
    """Bridges multimodal processing with Cortex message routing."""

    def __init__(self, processor: MultiModalProcessor, cortex):
        self.processor = processor
        self.cortex = cortex

    async def process_and_route(self, file_path: str, instruction: str = "") -> str:
        """Process a file and route the extracted text through Cortex.

        Example: process_and_route("contract.pdf", "review this contract")
        -> Processes PDF -> extracts text -> routes to Redline agent
        """
        processed = await self.processor.process(file_path)

        # Build a message that combines the instruction with the extracted content
        parts: list[str] = []
        if instruction:
            parts.append(instruction)

        parts.append(f"\n--- Processed {processed.input_type} from {processed.original_path} ---")
        parts.append(processed.text_content)

        if processed.metadata:
            meta_summary = ", ".join(f"{k}: {v}" for k, v in processed.metadata.items())
            parts.append(f"\n[Metadata: {meta_summary}]")

        message = "\n".join(parts)

        # Route through Cortex
        response = await self.cortex.process(message)
        return response
