from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _default_data_dir() -> Path:
    if env := os.environ.get("NEXUS_DATA_DIR"):
        return Path(env)
    if xdg := os.environ.get("XDG_DATA_HOME"):
        return Path(xdg) / "nexus"
    return Path.home() / ".local" / "share" / "nexus"


def _default_model_name() -> str:
    return os.environ.get("NEXUS_MODEL", "qwen3-8b-q4_k_m")


def _default_model_path() -> Optional[str]:
    return os.environ.get("NEXUS_MODEL_PATH")


def _default_llm_port() -> int:
    return int(os.environ.get("NEXUS_LLM_PORT", 8384))


def _default_log_level() -> str:
    return os.environ.get("NEXUS_LOG_LEVEL", "INFO")


def _default_provider() -> str:
    return os.environ.get("NEXUS_DEFAULT_PROVIDER", "local")

def _default_openai_key() -> Optional[str]:
    return os.environ.get("NEXUS_OPENAI_KEY")

def _default_anthropic_key() -> Optional[str]:
    return os.environ.get("NEXUS_ANTHROPIC_KEY")

def _default_openai_model() -> str:
    return os.environ.get("NEXUS_OPENAI_MODEL", "gpt-4o-mini")

def _default_anthropic_model() -> str:
    return os.environ.get("NEXUS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


@dataclass
class NexusConfig:
    data_dir: Path = field(default_factory=_default_data_dir)
    model_name: str = field(default_factory=_default_model_name)
    model_path: Optional[str] = field(default_factory=_default_model_path)
    llm_port: int = field(default_factory=_default_llm_port)
    log_level: str = field(default_factory=_default_log_level)
    default_provider: str = field(default_factory=_default_provider)
    openai_api_key: Optional[str] = field(default_factory=_default_openai_key)
    anthropic_api_key: Optional[str] = field(default_factory=_default_anthropic_key)
    openai_model: str = field(default_factory=_default_openai_model)
    anthropic_model: str = field(default_factory=_default_anthropic_model)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nexus.db"

    @property
    def models_dir(self) -> Path:
        models = self.data_dir / "models"
        models.mkdir(parents=True, exist_ok=True)
        return models
