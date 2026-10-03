import asyncio

from src.core.agent_plan import AgentPlanStep, ToolDescriptor
from src.core.tool_registry import ToolExecutionContext, ToolExecutionResult, ToolRegistry, ToolRegistryError


def test_tool_registry_supports_async_extension_handlers() -> None:
    registry = ToolRegistry()

    async def handler(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
        assert step.tool == "skill:portrait:protect_identity"
        assert context.current_image == "current"
        return ToolExecutionResult(message="ok", output_image="edited", details={"safe": True})

    registry.register(
        ToolDescriptor(
            name="skill:portrait:protect_identity",
            description="Keep portrait identity stable.",
            execution="skill",
        ),
        source="skill",
        handler=handler,
    )
    result = asyncio.run(
        registry.execute(
            AgentPlanStep(id="protect", tool="skill:portrait:protect_identity"),
            context=ToolExecutionContext(source_image="source", current_image="current"),
        ),
    )
    assert result.output_image == "edited"
    assert registry.summaries()[0]["bound"] is True


def test_tool_registry_rejects_unbound_or_misnamed_extensions() -> None:
    registry = ToolRegistry()
    try:
        registry.register(
            ToolDescriptor(name="portrait", description="bad", execution="skill"),
            source="skill",
        )
    except ToolRegistryError as exc:
        assert "skill:" in str(exc)
    else:
        raise AssertionError("Skill tool namespace should be enforced")

    registry.register(
        ToolDescriptor(name="mcp:metadata:read", description="read", execution="mcp"),
        source="mcp",
    )
    try:
        asyncio.run(
            registry.execute(
                AgentPlanStep(id="read", tool="mcp:metadata:read"),
                context=ToolExecutionContext(source_image="source", current_image="current"),
            ),
        )
    except ToolRegistryError as exc:
        assert "尚未绑定" in str(exc)
    else:
        raise AssertionError("unbound extension should fail explicitly")


def test_async_tool_enforces_json_schema() -> None:
    registry = ToolRegistry()

    async def handler(step, context):
        return ToolExecutionResult(message="ok")

    registry.register(
        ToolDescriptor(
            name="mcp:guarded:tool",
            description="guarded",
            execution="mcp",
            input_schema={
                "json_schema": '{"type":"object","required":["value"],"properties":{"value":{"type":"string"}}}',
            },
        ),
        source="mcp",
        handler=handler,
    )
    result = asyncio.run(registry.execute(
        AgentPlanStep(id="guarded", tool="mcp:guarded:tool", params={"value": "ok"}),
        context=ToolExecutionContext(source_image="source", current_image="current"),
    ))
    assert result.message == "ok"
    try:
        asyncio.run(registry.execute(
            AgentPlanStep(id="guarded", tool="mcp:guarded:tool", params={"value": 1}),
            context=ToolExecutionContext(source_image="source", current_image="current"),
        ))
    except ToolRegistryError as exc:
        assert "Schema" in str(exc)
    else:
        raise AssertionError("invalid tool input should be rejected")
