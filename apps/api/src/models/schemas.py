from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Config / Endpoint ──────────────────────────────────────────

class ModelEndpoint(BaseModel):
    host: str
    key: str = ""
    model: str


class CapabilityCheckRequest(ModelEndpoint):
    role: Literal["analysis", "edit"] = "analysis"


class CapabilityCheckResponse(BaseModel):
    reachable: bool
    model_available: bool | None = None
    protocol: str
    capabilities: list[str] = Field(default_factory=list)
    message: str = ""


# ── Agent Run ──────────────────────────────────────────────────

class AgentConfig(BaseModel):
    analysis: ModelEndpoint
    edit: ModelEndpoint


class AgentBudget(BaseModel):
    deadline_seconds: int = Field(default=900, ge=30, le=3600)
    max_image_calls: int = Field(default=2, ge=1, le=3)


class AgentContent(BaseModel):
    content: str = ""
    image: str = ""


class AgentRunRequest(BaseModel):
    config: AgentConfig
    budget: AgentBudget = Field(default_factory=AgentBudget)
    content: AgentContent = Field(..., description="User's text prompt and image (base64 data URL)")
    styles: list[dict[str, str]] = Field(default_factory=lambda: [{"style": ""}])
    plan: dict[str, Any] | None = None
    runId: str | None = None
    approved: bool = False
    origin: Literal["direct", "assistant_handoff"] = "direct"
    workspaceId: str | None = None
    versionId: str | None = None


class AgentRunResponse(BaseModel):
    analysis: dict[str, Any]
    analysis_raw: str
    images: list[str]
    text: str | None = None
    plan: dict[str, Any] | None = None
    tool_trace: dict[str, Any] | None = None


class AssistantHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class AssistantRequest(BaseModel):
    """One contextual Assistant turn; it never invokes the image-edit model."""

    config: AgentConfig
    content: AgentContent = Field(..., description="Current image and the user's Assistant request")
    history: list[AssistantHistoryMessage] = Field(default_factory=list, max_length=12)
    current_version: str = Field(default="current", max_length=128)
    session_id: str | None = None
    workspace_id: str | None = None


class AssistantResponse(BaseModel):
    session_id: str | None = None
    message_id: str | None = None
    reply: str
    intent: Literal["answer", "edit", "workflow"]
    action: Literal["none", "preview_edit", "workflow"]
    suggested_prompt: str = ""
    trace: dict[str, Any] = Field(default_factory=dict)


class AssistantSessionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=128)
    asset_id: str = ""
    current_version: str = Field(default="current", max_length=128)


class BatchToolRequest(BaseModel):
    assetIds: list[str] = Field(default_factory=list)
    excludeAssetIds: list[str] = Field(default_factory=list)
    feedbackId: str | None = None
    referenceAssetId: str | None = None
    operation: Literal["adjustments", "white_balance", "style", "reference_color"]
    adjustments: dict[str, float] = Field(default_factory=dict)
    styleId: str | None = None
    referenceImage: str | None = None
    priority: Literal["high", "normal", "low"] = "normal"


# ── Editor Run ─────────────────────────────────────────────────

class EditorConfig(BaseModel):
    edit: ModelEndpoint


class EditorMarkSchema(BaseModel):
    """A region mark on the image (relative coordinates 0-1)."""
    center_x: float = Field(..., ge=0, le=1, description="Center X relative to image width")
    center_y: float = Field(..., ge=0, le=1, description="Center Y relative to image height")
    radius: float = Field(..., ge=0, le=1, description="Radius relative to min(width, height)")
    description: str = ""


class EditorRunRequest(BaseModel):
    config: EditorConfig
    image: str = Field(..., description="Source image as base64 data URL")
    marks: list[EditorMarkSchema] = Field(default_factory=list)
    styles: list[dict[str, str]] = Field(default_factory=lambda: [{"style": ""}])
    image_config: dict[str, Any] | None = None
    run_id: str | None = None
    workspace_id: str | None = None
    version_id: str | None = None
    asset_id: str | None = None


class EditorRunResponse(BaseModel):
    run_id: str | None = None
    images: list[str]
    text: str | None = None
    validation: dict[str, Any] | None = None


# ── Health ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
