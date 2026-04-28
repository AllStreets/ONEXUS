from __future__ import annotations

import os
from pathlib import Path

import pytest

from nexus.config import NexusConfig


def test_default_config_paths(tmp_path, monkeypatch):
    """Defaults end with 'nexus', 'nexus.db', model is 'qwen3-8b-q4_k_m'."""
    # Isolate from any env vars that might interfere
    monkeypatch.delenv("NEXUS_DATA_DIR", raising=False)
    monkeypatch.delenv("NEXUS_MODEL", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    # Point HOME to tmp_path so data_dir creation doesn't touch real home
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg = NexusConfig()

    assert cfg.data_dir.name == "nexus"
    assert cfg.db_path.name == "nexus.db"
    assert cfg.model_name == "qwen3-8b-q4_k_m"


def test_config_from_env(tmp_path, monkeypatch):
    """NEXUS_DATA_DIR and NEXUS_MODEL env vars override defaults."""
    custom_data = tmp_path / "custom_data"
    monkeypatch.setenv("NEXUS_DATA_DIR", str(custom_data))
    monkeypatch.setenv("NEXUS_MODEL", "llama3-70b")

    cfg = NexusConfig()

    assert cfg.data_dir == custom_data
    assert cfg.model_name == "llama3-70b"


def test_config_creates_data_dir(tmp_path):
    """data_dir is created if it doesn't exist."""
    target = tmp_path / "brand_new_dir"
    assert not target.exists()

    cfg = NexusConfig(data_dir=target)

    assert target.exists()
    assert target.is_dir()


def test_config_default_provider(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.default_provider == "local"

def test_config_default_provider_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DEFAULT_PROVIDER", "openai")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.default_provider == "openai"

def test_config_api_keys_default_none(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_api_key is None
    assert cfg.anthropic_api_key is None

def test_config_api_keys_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_OPENAI_KEY", "sk-test-123")
    monkeypatch.setenv("NEXUS_ANTHROPIC_KEY", "ant-test-456")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_api_key == "sk-test-123"
    assert cfg.anthropic_api_key == "ant-test-456"

def test_config_model_names_default(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_model == "gpt-4o-mini"
    assert cfg.anthropic_model == "claude-sonnet-4-20250514"

def test_config_model_names_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("NEXUS_ANTHROPIC_MODEL", "claude-opus-4-20250514")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_model == "gpt-4o"
    assert cfg.anthropic_model == "claude-opus-4-20250514"
