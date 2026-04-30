from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Request models ──────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to process")
    context: dict[str, Any] = Field(default_factory=dict, description="Optional context")


class TrustAdjustRequest(BaseModel):
    delta: int = Field(..., ge=-100, le=100, description="Trust score adjustment")
    reason: str = Field(..., min_length=1, description="Reason for adjustment")


class PublishEventRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Event topic")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    source: str = Field(default="api", description="Event source identifier")


# ── Response models ─────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    response: str
    module: Optional[str] = None


class ModuleInfo(BaseModel):
    name: str
    description: str
    version: str
    requires_network: bool
    allowed: bool
    trust: int
    network_allowed: bool


class ModuleListResponse(BaseModel):
    modules: list[ModuleInfo]
    count: int


class ModuleDetailResponse(BaseModel):
    module: ModuleInfo


class PolicyActionResponse(BaseModel):
    module: str
    action: str
    success: bool


class MemoryWorkingResponse(BaseModel):
    entries: dict[str, Any]


class MemoryEpisodicResponse(BaseModel):
    results: list[dict[str, Any]]
    count: int


class MemorySemanticResponse(BaseModel):
    results: list[dict[str, Any]]
    count: int


class MemoryEraseResponse(BaseModel):
    success: bool
    message: str


class ChronicleEntry(BaseModel):
    event_id: str
    timestamp: str
    source: str
    action: str
    payload: dict[str, Any]


class ChronicleQueryResponse(BaseModel):
    entries: list[ChronicleEntry]
    count: int


class ChronicleStatsResponse(BaseModel):
    total_events: int
    by_action: dict[str, int]
    by_source: dict[str, int]


class TrustScoreResponse(BaseModel):
    module: str
    trust: int
    allowed: bool
    network_allowed: bool


class TrustAllResponse(BaseModel):
    scores: list[TrustScoreResponse]


class TrustHistoryEntry(BaseModel):
    timestamp: str
    delta: int
    new_trust: int
    reason: str


class TrustDetailResponse(BaseModel):
    module: str
    trust: int
    allowed: bool
    network_allowed: bool
    history: list[TrustHistoryEntry]


class TrustAdjustResponse(BaseModel):
    module: str
    new_trust: int
    delta: int
    reason: str


class TopicListResponse(BaseModel):
    topics: list[str]


class PublishEventResponse(BaseModel):
    success: bool
    topic: str


class SystemStatusResponse(BaseModel):
    version: str
    data_dir: str
    db_exists: bool
    model: str
    llm_port: int
    modules_loaded: int
    default_provider: str


class HealthCheckResponse(BaseModel):
    status: str
    db_accessible: bool
    llm_available: Optional[bool] = None


class SystemConfigResponse(BaseModel):
    data_dir: str
    model_name: str
    llm_port: int
    log_level: str
    default_provider: str
    openai_configured: bool
    anthropic_configured: bool
    telegram_configured: bool
    discord_configured: bool


# ── Provider management ────────────────────────────────────────────────────

class RegisterProviderRequest(BaseModel):
    provider: str = Field(
        ...,
        description="Provider type: 'openai', 'anthropic', or 'local'",
    )
    api_key: Optional[str] = Field(
        None,
        description="API key (required for openai/anthropic)",
    )
    model: Optional[str] = Field(
        None,
        description="Model name (e.g. 'gpt-4o', 'claude-sonnet-4-20250514', 'qwen3-8b-q4_k_m')",
    )
    base_url: Optional[str] = Field(
        None,
        description="Base URL for local provider (default: http://localhost:8384)",
    )
    set_default: bool = Field(
        False,
        description="Set this provider as the default for inference",
    )


class ProviderInfoResponse(BaseModel):
    name: str
    healthy: bool
    is_default: bool


class ProviderListResponse(BaseModel):
    providers: list[ProviderInfoResponse]
    default: str


class RegisterProviderResponse(BaseModel):
    provider: str
    registered: bool
    is_default: bool
    message: str


class RemoveProviderResponse(BaseModel):
    provider: str
    removed: bool
    message: str
