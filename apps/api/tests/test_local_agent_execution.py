import asyncio
from unittest.mock import AsyncMock, patch

from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.orchestration import run_agent
from src.core.types import AgentImageAnalysis


PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'


def test_local_plan_does_not_call_image_model() -> None:
    plan = AgentPlan(
        goal='降低饱和度', execution='local',
        steps=[
            AgentPlanStep(id='balance', tool='apply_adjustments', params={'adjustments': {'saturation': -8}}),
            AgentPlanStep(id='validate', tool='validate_result', depends_on=['balance']),
        ],
    )
    analysis = '{"imageType":"landscape","imageTypeReason":"场景","deficiencies":[],"summary":"正常","editPrompt":"保持原图"}'
    async def completion(**kwargs):
        return {'text': analysis, 'trace': {'model': 'analysis', 'status': 'completed'}}

    async def run():
        checkpoints = []

        async def on_tool(tool_run, output_image, attempt):
            checkpoints.append((tool_run.step_id, output_image, attempt))

        with patch('src.core.orchestration.litellm_completion', new=completion), \
             patch('src.core.orchestration.litellm_image_completion', new_callable=AsyncMock) as image:
            result = await run_agent(
                analysis_host='https://example.com/v1', analysis_api_key='x', analysis_model='analysis',
                edit_host='https://example.com/v1', edit_api_key='x', edit_model='image',
                image_data_url=PIXEL, user_prompt='降低饱和度', planned_plan=plan,
                on_tool=on_tool,
            )
            image.assert_not_awaited()
            assert result[2][0].startswith('data:image/')
            assert result[5]['runs'][0]['tool'] == 'apply_adjustments'
            assert [item[0] for item in checkpoints] == ['balance', 'validate']
            assert [item[2] for item in checkpoints] == [1, 1]

    asyncio.run(run())


def test_approved_analysis_snapshot_skips_second_analysis_call() -> None:
    plan = AgentPlan(
        goal='降低饱和度', execution='local',
        steps=[
            AgentPlanStep(id='balance', tool='apply_adjustments', params={'adjustments': {'saturation': -8}}),
            AgentPlanStep(id='validate', tool='validate_result', depends_on=['balance']),
        ],
    )
    snapshot = AgentImageAnalysis('landscape', '场景', [], '已分析', '降低饱和度')

    async def run():
        with patch('src.core.orchestration.litellm_completion', new_callable=AsyncMock) as analysis:
            result = await run_agent(
                analysis_host='https://example.com/v1', analysis_api_key='x', analysis_model='analysis',
                edit_host='https://example.com/v1', edit_api_key='x', edit_model='image',
                image_data_url=PIXEL, user_prompt='降低饱和度', planned_plan=plan,
                planned_analysis=snapshot, planned_analysis_raw='frozen-analysis',
            )
            analysis.assert_not_awaited()
            assert result[0] is snapshot
            assert result[1] == 'frozen-analysis'
            assert result[5]['aiCalls'][0]['protocol'] == 'approved-analysis'

    asyncio.run(run())


def test_ai_trace_keeps_raw_provider_validation() -> None:
    plan = AgentPlan(
        goal='修复曝光', execution='ai',
        steps=[
            AgentPlanStep(id='edit', tool='apply_ai_edit', params={'edit_prompt': '修复曝光'}),
            AgentPlanStep(id='validate', tool='validate_result', depends_on=['edit']),
        ],
    )
    analysis = '{"imageType":"landscape","imageTypeReason":"场景","deficiencies":[],"summary":"正常","editPrompt":"修复曝光"}'

    async def run():
        async def completion(**kwargs):
            return {'text': analysis, 'trace': {'model': 'analysis', 'status': 'completed'}}

        with patch('src.core.orchestration.litellm_completion', new=completion), \
             patch('src.core.orchestration.litellm_image_completion', new_callable=AsyncMock) as image:
            image.return_value = {'images': [PIXEL], 'trace': {'model': 'image', 'status': 'completed'}}
            result = await run_agent(
                analysis_host='https://example.com/v1', analysis_api_key='x', analysis_model='analysis',
                edit_host='https://example.com/v1', edit_api_key='x', edit_model='image',
                image_data_url=PIXEL, user_prompt='修复曝光', planned_plan=plan,
            )
            assert result[5]['aiCalls'][-1]['rawValidation']['metrics']['outputWidth'] == 2

    asyncio.run(run())
