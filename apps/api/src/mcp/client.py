"""Minimal MCP HTTP client boundary for future external tools.

The client does not persist credentials, does not execute arbitrary local
processes, and requires an enabled registered server. Concrete servers can be
added later without changing the Agent Runtime contract.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from .registry import McpServerConfig, mcp_server_registry


class McpClientError(RuntimeError):
    pass


class McpHttpClient:
    def __init__(self, server: McpServerConfig, *, bearer_token: str | None = None):
        if not server.enabled:
            raise McpClientError(f"MCP server is disabled: {server.id}")
        if server.transport != "http" or not server.url:
            raise McpClientError("Only enabled HTTP MCP servers are supported by this client")
        self.server = server
        self.headers = {"Content-Type": "application/json"}
        if bearer_token:
            self.headers["Authorization"] = f"Bearer {bearer_token}"

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.server.timeout_seconds),
                follow_redirects=False,
            ) as client:
                response = await client.post(self.server.url or "", headers=self.headers, json=payload)
        except httpx.TimeoutException as exc:
            raise McpClientError(f"MCP 请求超时: {self.server.id}") from exc
        except httpx.HTTPError as exc:
            raise McpClientError(f"MCP 网络请求失败: {self.server.id}") from exc
        if response.status_code >= 400:
            raise McpClientError(f"MCP HTTP 请求失败: {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise McpClientError("MCP 返回的不是有效 JSON") from exc
        if not isinstance(body, dict):
            raise McpClientError("MCP 返回结构无效")
        if body.get("error"):
            raise McpClientError(str(body["error"]))
        result = body.get("result", {})
        if not isinstance(result, dict):
            raise McpClientError("MCP result 结构无效")
        return result

    async def initialize(self) -> dict[str, Any]:
        return await self._request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "visual-workbench", "version": "0.1.0"},
        })

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._request("tools/list")
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not name.strip():
            raise McpClientError("MCP 工具名不能为空")
        return await self._request("tools/call", {"name": name, "arguments": arguments})


def get_mcp_client(server_id: str, *, bearer_token: str | None = None) -> McpHttpClient:
    server = mcp_server_registry.get(server_id)
    if server is None:
        raise McpClientError(f"Unknown MCP server: {server_id}")
    return McpHttpClient(server, bearer_token=bearer_token)
