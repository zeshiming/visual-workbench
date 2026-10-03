"""Provider-neutral Tool Registry contracts for the custom Agent Harness.

The registry is deliberately separate from the Agent Loop. A native tool,
model adapter, MCP tool, or Skill can register the same descriptor and an
optional async handler without changing planning, approval, tracing, or
recovery code.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from .agent_plan import AgentPlanStep, TOOL_CATALOG, ToolDescriptor


ToolSource = Literal["native", "model", "mcp", "skill"]


@dataclass(frozen=True)
class ToolExecutionContext:
    source_image: str
    current_image: str
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolExecutionResult:
    message: str
    output_image: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[[AgentPlanStep, ToolExecutionContext], Awaitable[ToolExecutionResult]]
SyncToolHandler = Callable[[AgentPlanStep, ToolExecutionContext], ToolExecutionResult]


@dataclass(frozen=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    source: ToolSource
    handler: ToolHandler | None = None
    sync_handler: SyncToolHandler | None = None


class ToolRegistryError(RuntimeError):
    pass


class ToolRegistry:
    def __init__(self, descriptors: tuple[ToolDescriptor, ...] = ()) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        for descriptor in descriptors:
            source: ToolSource = "model" if descriptor.execution == "ai" else "native"
            self.register(descriptor, source=source)

    def register(
        self,
        descriptor: ToolDescriptor,
        *,
        source: ToolSource,
        handler: ToolHandler | None = None,
        sync_handler: SyncToolHandler | None = None,
        replace: bool = False,
    ) -> None:
        if descriptor.name in self._tools and not replace:
            raise ToolRegistryError(f"工具已注册: {descriptor.name}")
        if source == "mcp" and not descriptor.name.startswith("mcp:"):
            raise ToolRegistryError("MCP 工具名必须使用 mcp: 前缀")
        if source == "skill" and not descriptor.name.startswith("skill:"):
            raise ToolRegistryError("Skill 工具名必须使用 skill: 前缀")
        self._tools[descriptor.name] = RegisteredTool(
            descriptor=descriptor,
            source=source,
            handler=handler,
            sync_handler=sync_handler,
        )

    def register_sync(self, descriptor: ToolDescriptor, *, source: ToolSource,
                      handler: SyncToolHandler, replace: bool = False) -> None:
        self.register(descriptor, source=source, sync_handler=handler, replace=replace)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def summaries(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.descriptor.name,
                "description": tool.descriptor.description,
                "execution": tool.descriptor.execution,
                "source": tool.source,
                "riskLevel": tool.descriptor.risk_level,
                "timeoutSeconds": tool.descriptor.timeout_seconds,
                "idempotent": tool.descriptor.idempotent,
                "bound": tool.handler is not None or tool.sync_handler is not None,
            }
            for tool in self._tools.values()
        ]

    def planner_context(self, *, max_chars: int = 8_000) -> str:
        lines = []
        for item in self._tools.values():
            if item.handler is None and item.sync_handler is None:
                continue
            lines.append(
                f"- {item.descriptor.name} [{item.source}] risk={item.descriptor.risk_level}: "
                f"{item.descriptor.description}; schema={item.descriptor.input_schema}"
            )
        return "\n".join(lines)[:max_chars]

    async def execute(
        self,
        step: AgentPlanStep,
        *,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        registered = self.get(step.tool)
        if registered is None:
            raise ToolRegistryError(f"工具未注册: {step.tool}")
        if registered.handler is None:
            raise ToolRegistryError(f"工具尚未绑定执行器: {step.tool}")
        self._validate_input(registered.descriptor, step.params)
        try:
            return await asyncio.wait_for(
                registered.handler(step, context),
                timeout=registered.descriptor.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ToolRegistryError(
                f"工具执行超时（{registered.descriptor.timeout_seconds}s）: {step.tool}",
            ) from exc

    def execute_sync(self, step: AgentPlanStep, *, context: ToolExecutionContext) -> ToolExecutionResult:
        registered = self.get(step.tool)
        if registered is None:
            raise ToolRegistryError(f"工具未注册: {step.tool}")
        if registered.sync_handler is None:
            raise ToolRegistryError(f"工具尚未绑定同步执行器: {step.tool}")
        self._validate_input(registered.descriptor, step.params)
        return registered.sync_handler(step, context)

    @staticmethod
    def _validate_input(descriptor: ToolDescriptor, params: dict[str, Any]) -> None:
        raw_schema = descriptor.input_schema.get("json_schema") if descriptor.input_schema else None
        if not raw_schema:
            return
        try:
            schema = json.loads(raw_schema) if isinstance(raw_schema, str) else raw_schema
            Draft202012Validator(schema).validate(params)
        except (json.JSONDecodeError, SchemaError) as exc:
            raise ToolRegistryError(f"工具输入 Schema 无效: {descriptor.name}") from exc
        except ValidationError as exc:
            raise ToolRegistryError(f"工具输入不符合 Schema: {descriptor.name}: {exc.message}") from exc


tool_registry = ToolRegistry(TOOL_CATALOG)
