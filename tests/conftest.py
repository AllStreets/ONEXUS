from __future__ import annotations

import pytest

from nexus.config import NexusConfig


@pytest.fixture
def tmp_config(tmp_path):
    """NexusConfig pointing at a temp directory, isolated per test."""
    return NexusConfig(data_dir=tmp_path / "nexus_data")


@pytest.fixture
def mock_llm_response():
    """Factory that returns an async callable returning a fixed string."""
    def factory(response_text: str = "mock response"):
        async def _mock(*args, **kwargs) -> str:
            return response_text
        return _mock
    return factory
