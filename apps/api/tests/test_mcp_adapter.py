import asyncio
from unittest.mock import AsyncMock, patch

from src.core.agent_plan import AgentPlanStep
from src.core.policy import validate_agent_plan_shape
from src.core.tool_registry import ToolExecutionContext, tool_registry
from src.core.tool_registry import ToolExecutionResult
from src.core.orchestration import run_agent
from src.core.agent_plan import AgentPlan
from src.mcp.adapter import discover_mcp_tools
from src.mcp.registry import McpServerConfig, mcp_server_registry
import src.routers.agent as agent_router


def test_mcp_discovery_registers_namespaced_async_handler() -> None:
    server_id = "test-server"
    mcp_server_registry.register(McpServerConfig(id=server_id, name="Test", transport="http", url="https://example.com", enabled=True, allowed_tools=["read-photo"]))

    class FakeClient:
        async def initialize(self): return {}
        async def list_tools(self): return [{"name": "read-photo", "description": "read", "inputSchema": {"type": "object"}}]
        async def call_tool(self, name, arguments): return {"name": name, "arguments": arguments}

    async def run():
        with patch('src.mcp.adapter.get_mcp_client', return_value=FakeClient()):
            names = await discover_mcp_tools(server_id)
        assert names == ['mcp:test-server:read-photo']
        result = await tool_registry.execute(
            AgentPlanStep(id='mcp', tool=names[0], params={'assetId': 'a'}),
            context=ToolExecutionContext(source_image='source', current_image='current'),
        )
        assert result.details['mcpResult']['name'] == 'read-photo'
    asyncio.run(run())


def test_unregistered_extension_is_rejected_before_execution() -> None:
    plan = __import__('src.core.agent_plan', fromlist=['AgentPlan']).AgentPlan(
        goal='extension', execution='local',
        steps=[AgentPlanStep(id='mcp', tool='mcp:not-registered:tool'), AgentPlanStep(id='check', tool='validate_result', depends_on=['mcp'])],
    )
    try:
        validate_agent_plan_shape(plan)
    except ValueError as exc:
        assert '尚未注册' in str(exc)
    else:
        raise AssertionError('unregistered MCP tool should be rejected')


def test_registered_async_mcp_tool_runs_inside_local_plan():
    name = 'mcp:test-server:local-read'
    async def handler(step, context):
        return ToolExecutionResult('MCP finished', details={'ok': True})
    descriptor = __import__('src.core.agent_plan', fromlist=['ToolDescriptor']).ToolDescriptor(
        name=name, description='read', execution='mcp',
    )
    tool_registry.register(descriptor, source='mcp', handler=handler, replace=True)
    plan = AgentPlan(goal='MCP local plan', execution='local', steps=[
        __import__('src.core.agent_plan', fromlist=['AgentPlanStep']).AgentPlanStep(id='mcp', tool=name),
        __import__('src.core.agent_plan', fromlist=['AgentPlanStep']).AgentPlanStep(id='validate', tool='validate_result', depends_on=['mcp']),
    ])
    pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'
    async def completion(**kwargs):
        return {'text': '{"imageType":"landscape","imageTypeReason":"x","deficiencies":[],"summary":"x","editPrompt":"x"}', 'trace': {}}
    async def run():
        with patch('src.core.orchestration.litellm_completion', new=completion), patch('src.core.orchestration.litellm_image_completion', new_callable=AsyncMock) as image:
            result = await run_agent(analysis_host='https://example.com/v1', analysis_api_key='x', analysis_model='a', edit_host='https://example.com/v1', edit_api_key='x', edit_model='e', image_data_url=pixel, planned_plan=plan)
            image.assert_not_awaited()
            assert result[5]['runs'][0]['tool'] == name
    asyncio.run(run())


def test_mcp_discovery_does_not_authorize_unlisted_tool():
    server_id = "allow-list-test"
    mcp_server_registry.register(McpServerConfig(
        id=server_id, name="Allow list", transport="http", url="https://example.com", enabled=True,
    ))

    class FakeClient:
        async def initialize(self): return {}
        async def list_tools(self): return [{"name": "dangerous-tool"}]

    async def run():
        with patch('src.mcp.adapter.get_mcp_client', return_value=FakeClient()):
            names = await discover_mcp_tools(server_id)
        assert names == ['mcp:allow-list-test:dangerous-tool']
        assert tool_registry.get(names[0]) is None

    asyncio.run(run())


def test_mcp_connection_check_only_initializes_server():
    server_id = "connection-check-test"
    mcp_server_registry.register(McpServerConfig(
        id=server_id, name="Connection check", transport="http", url="https://example.com", enabled=True,
    ))

    class FakeClient:
        async def initialize(self): return {"protocolVersion": "2025-06-18"}

    async def run():
        with patch.object(agent_router, 'get_mcp_client', return_value=FakeClient()):
            result = await agent_router.check_mcp_extension(server_id)
        assert result['reachable'] is True
        assert result['protocolVersion'] == '2025-06-18'
        assert mcp_server_registry.get(server_id).allowed_tools == []

    asyncio.run(run())
