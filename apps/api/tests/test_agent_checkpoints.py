import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine, select

import src.routers.agent as agent_router
from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.models.schemas import AgentRunRequest
from src.models.settings import AgentPlanRecord, AgentRunRecord, AgentStepRecord


def test_final_trace_does_not_duplicate_step_checkpoint():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
        agent_router._persist_agent_run('checkpoint-run', status='running')
        with Session(engine) as db:
            db.add(AgentStepRecord(
                id='checkpoint-run:checkpoint:1:balance',
                run_id='checkpoint-run', step_id='balance', tool='apply_adjustments',
                status='executed', attempt=1,
                output_json=json.dumps({'stepId': 'balance'}),
                output_artifact_path='/tmp/checkpoint.json',
                started_at=1, ended_at=2,
            ))
            db.commit()
        with patch.object(agent_router, 'save_agent_result_file', return_value='/tmp/result.json'):
            agent_router._persist_agent_run(
                'checkpoint-run',
                status='completed',
                trace={'runs': [{'stepId': 'balance', 'tool': 'apply_adjustments', 'status': 'executed'}]},
            )
    with Session(engine) as db:
        rows = db.exec(select(AgentStepRecord).where(AgentStepRecord.run_id == 'checkpoint-run')).all()
        assert len(rows) == 1
        assert rows[0].output_artifact_path == '/tmp/checkpoint.json'


def test_agent_step_file_is_atomic_and_readable():
    from src.models import settings

    with tempfile.TemporaryDirectory() as directory:
        with patch.object(settings, 'WORKSPACE_IMAGES_DIR', directory), \
             patch.object(agent_router, 'WORKSPACE_IMAGES_DIR', directory):
            path = settings.save_agent_step_file('run-1', 2, 'step:one', 'data:image/png;base64,abc')
            assert Path(path).is_file()
            assert json.loads(Path(path).read_text())['dataUrl'].startswith('data:image/')


def test_local_resume_skips_completed_checkpointed_steps():
    from src.models import settings

    pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'
    plan = AgentPlan(
        goal='本地恢复', execution='local',
        steps=[
            AgentPlanStep(id='balance', tool='apply_adjustments', params={'adjustments': {'saturation': -5}}),
            AgentPlanStep(id='validate', tool='validate_result', depends_on=['balance']),
        ],
    )
    request = AgentRunRequest(
        config={'analysis': {'host': 'https://example.com/v1', 'model': 'analysis'},
                'edit': {'host': 'https://example.com/v1', 'model': 'image'}},
        content={'image': pixel, 'content': '本地恢复'}, approved=True,
    )
    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine('sqlite://')
        SQLModel.metadata.create_all(engine)
        with patch.object(settings, 'WORKSPACE_IMAGES_DIR', directory), \
             patch.object(agent_router, 'WORKSPACE_IMAGES_DIR', directory), \
             patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
            with Session(engine) as db:
                approval_id = agent_router.save_preview(
                    db, request, plan,
                    {'imageType': 'landscape', 'imageTypeReason': '场景', 'deficiencies': [], 'summary': '正常', 'editPrompt': '本地恢复'},
                    analysis_raw=json.dumps({'imageType': 'landscape', 'imageTypeReason': '场景', 'deficiencies': [], 'summary': '正常', 'editPrompt': '本地恢复'}),
                )
                request.plan = {**plan.model_dump(), 'approval_id': approval_id}
                record = AgentRunRecord(id='resume-run', status='interrupted', plan_json=plan.model_dump_json())
                db.add(record)
                preview = db.get(AgentPlanRecord, approval_id)
                preview.run_id = 'resume-run'
                db.add(preview)
                step_path = settings.save_agent_step_file('resume-run', 1, 'balance', pixel)
                db.add(AgentStepRecord(
                    id='resume-run:checkpoint:1:balance', run_id='resume-run', step_id='balance',
                    tool='apply_adjustments', status='executed', attempt=1,
                    output_artifact_path=step_path, output_json='{}', started_at=1, ended_at=2,
                ))
                db.commit()
            response = asyncio.run(agent_router.resume_local_agent_run('resume-run', request))
            assert response.media_type == 'application/x-ndjson'
            assert 'resume-run' in agent_router._AGENT_CONTROLS
            agent_router._AGENT_CONTROLS.pop('resume-run', None)
            try:
                asyncio.run(agent_router.resume_local_agent_run('resume-run', request))
            except Exception as exc:
                assert getattr(exc, 'status_code', None) == 409
            else:
                raise AssertionError('a second worker must not claim the active lease')
