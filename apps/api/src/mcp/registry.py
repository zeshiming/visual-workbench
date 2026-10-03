"""MCP server configuration registry; transport clients are added separately."""

from __future__ import annotations

from typing import Literal
import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


class McpServerConfig(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    transport: Literal["http", "stdio"]
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list, max_length=128)
    secret_ref: str | None = Field(default=None, max_length=128)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    enabled: bool = False

    @model_validator(mode="after")
    def validate_transport_config(self) -> "McpServerConfig":
        if self.transport == "http":
            if not self.url:
                raise ValueError("HTTP MCP server requires url")
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("MCP url must use http or https")
        elif self.enabled:
            raise ValueError("stdio MCP servers are not enabled in the current no-sandbox runtime")
        if self.secret_ref and not re.fullmatch(r"[A-Za-z0-9_.:-]+", self.secret_ref):
            raise ValueError("secret_ref 只能包含字母、数字、点、下划线、冒号或连字符")
        return self


class McpServerRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, McpServerConfig] = {}

    def register(self, server: McpServerConfig) -> None:
        self._servers[server.id] = server

    def get(self, server_id: str) -> McpServerConfig | None:
        return self._servers.get(server_id)

    def remove(self, server_id: str) -> bool:
        return self._servers.pop(server_id, None) is not None

    def set_enabled(self, server_id: str, enabled: bool) -> McpServerConfig:
        server = self._servers.get(server_id)
        if server is None:
            raise KeyError(server_id)
        if server.transport == "stdio" and enabled:
            raise ValueError("当前无 Sandbox 运行时不允许启用 stdio MCP")
        updated = server.model_copy(update={"enabled": enabled})
        self._servers[server_id] = updated
        return updated

    def summaries(self) -> list[dict[str, str | bool | int]]:
        return [
            {
                "id": item.id,
                "name": item.name,
                "transport": item.transport,
                "enabled": item.enabled,
                "timeoutSeconds": item.timeout_seconds,
                "allowedTools": item.allowed_tools,
            }
            for item in self._servers.values()
        ]


mcp_server_registry = McpServerRegistry()
