"""Bind discovered MCP tools into the shared Agent Tool Registry."""

from __future__ import annotations

import json
import re
from typing import Any

from .client import get_mcp_client
from .registry import mcp_server_registry
from ..core.tool_registry import ToolExecutionContext, ToolExecutionResult, tool_registry
from ..core.agent_plan import AgentPlanStep, ToolDescriptor


def _tool_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "tool"


async def discover_mcp_tools(server_id: str, *, bearer_token: str | None = None) -> list[str]:
    server = mcp_server_registry.get(server_id)
    if server is None:
        raise ValueError(f"未知 MCP Server: {server_id}")
    client = get_mcp_client(server_id, bearer_token=bearer_token)
    await client.initialize()
    discovered = await client.list_tools()
    names: list[str] = []
    for item in discovered:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        remote_name = item["name"]
        registry_name = f"mcp:{_tool_id(server_id)}:{_tool_id(remote_name)}"
        input_schema = item.get("inputSchema") if isinstance(item.get("inputSchema"), dict) else {}

        # Discovery is read-only. A tool is executable only after the user
        # explicitly adds its remote name to the server allow-list.
        if remote_name not in server.allowed_tools:
            names.append(registry_name)
            continue

        async def handler(step: AgentPlanStep, context: ToolExecutionContext,
                          *, _remote_name: str = remote_name, _client=client) -> ToolExecutionResult:
            result = await _client.call_tool(_remote_name, step.params)
            output_image = result.get("image") if isinstance(result.get("image"), str) else None
            return ToolExecutionResult(
                message=f"MCP 工具 {_remote_name} 已完成。",
                output_image=output_image,
                details={"mcpResult": result},
            )

        descriptor = ToolDescriptor(
            name=registry_name,
            description=str(item.get("description") or f"MCP {remote_name}"),
            execution="mcp",
            risk_level="medium",
            timeout_seconds=server.timeout_seconds,
            idempotent=False,
            input_schema={"json_schema": json.dumps(input_schema, ensure_ascii=False)},
        )
        tool_registry.register(descriptor, source="mcp", handler=handler, replace=True)
        names.append(registry_name)
    return names
