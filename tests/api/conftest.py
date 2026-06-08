from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.council import CouncilModule
from nexus.api.server import KernelState, create_app


@pytest.fixture
def tmp_config(tmp_path):
    return NexusConfig(data_dir=tmp_path / "nexus_data")


@pytest.fixture
def kernel(tmp_config):
    """Build a real kernel with isolated temp DB."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()

    chronicle = Chronicle(str(tmp_config.db_path))
    chronicle.init_db()

    aegis = Aegis(str(tmp_config.db_path))
    aegis.init_db()

    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=tmp_config,
    )

    council = CouncilModule()
    cortex.register_module(council)
    aegis.set_policy("council", allowed=True)

    async def _mock_llm(msg):
        return f"mock response to: {msg}"

    cortex.set_llm(_mock_llm)

    return KernelState(
        config=tmp_config,
        cortex=cortex,
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
    )


@pytest.fixture
def app(kernel):
    """Create a FastAPI app with an injected kernel (bypasses real init)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from nexus.api.routes.messages import router as messages_router
    from nexus.api.routes.modules import router as modules_router
    from nexus.api.routes.memory import router as memory_router
    from nexus.api.routes.chronicle import router as chronicle_router
    from nexus.api.routes.trust import router as trust_router
    from nexus.api.routes.events import router as events_router
    from nexus.api.routes.system import router as system_router

    test_app = FastAPI()
    test_app.state.kernel = kernel
    test_app.include_router(messages_router)
    test_app.include_router(modules_router)
    test_app.include_router(memory_router)
    test_app.include_router(chronicle_router)
    test_app.include_router(trust_router)
    test_app.include_router(events_router)
    test_app.include_router(system_router)
    return test_app


@pytest_asyncio.fixture
async def client(app):
    """Async test client using httpx + ASGITransport."""
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
