from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from nexus.config import NexusConfig
from nexus.api.server import create_app, KernelState


class TestAppCreation:
    def test_create_app_returns_fastapi(self, tmp_path):
        """create_app should return a FastAPI instance with kernel state."""
        cfg = NexusConfig(data_dir=tmp_path / "nexus_test")
        app = create_app(config=cfg)

        from fastapi import FastAPI
        assert isinstance(app, FastAPI)
        assert hasattr(app.state, "kernel")
        assert isinstance(app.state.kernel, KernelState)

    def test_kernel_state_has_all_components(self, tmp_path):
        cfg = NexusConfig(data_dir=tmp_path / "nexus_test2")
        app = create_app(config=cfg)
        ks = app.state.kernel

        assert ks.config is not None
        assert ks.cortex is not None
        assert ks.engram is not None
        assert ks.chronicle is not None
        assert ks.aegis is not None
        assert ks.pulse is not None

    def test_create_app_with_default_config(self, tmp_path):
        """create_app without explicit config should use NexusConfig defaults."""
        import os
        os.environ["NEXUS_DATA_DIR"] = str(tmp_path / "nexus_default")
        try:
            app = create_app()
            assert app.state.kernel is not None
        finally:
            del os.environ["NEXUS_DATA_DIR"]

    def test_routers_mounted(self, tmp_path):
        """All API routers should be included in the app."""
        cfg = NexusConfig(data_dir=tmp_path / "nexus_routes")
        app = create_app(config=cfg)
        route_paths = [r.path for r in app.routes]

        assert "/api/messages" in route_paths or any("/api/messages" in p for p in route_paths)
        assert any("/api/system/status" in getattr(r, "path", "") for r in app.routes)

    def test_general_module_registered(self, tmp_path):
        cfg = NexusConfig(data_dir=tmp_path / "nexus_mod")
        app = create_app(config=cfg)
        ks = app.state.kernel
        assert "general" in ks.cortex.list_modules()
