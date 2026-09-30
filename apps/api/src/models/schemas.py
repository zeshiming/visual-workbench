from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Config / Endpoint ──────────────────────────────────────────

class ModelEndpoint(BaseModel):
    host: str
    key: str = ""
    model: str


# ── Agent Run ──────────────────────────────────────────────────

class AgentConfig(BaseModel):
    analysis: ModelEndpoint
    edit: ModelEndpoint


class AgentContent(BaseModel):
    content: str = ""
    image: str = ""


class AgentRunRequest(BaseModel):
    config: AgentConfig
    content: AgentContent = Field(..., description="User's text prompt and image (base64 data URL)")
    styles: list[dict[str, str]] = Field(default_factory=lambda: [{"style": ""}])


class AgentRunResponse(BaseModel):
    analysis: dict[str, Any]
    analysis_raw: str
    images: list[str]
    text: str | None = None
    plan: dict[str, Any] | None = None
    tool_trace: dict[str, Any] | None = None


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


class EditorRunResponse(BaseModel):
    images: list[str]
    text: str | None = None


# ── Health ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
