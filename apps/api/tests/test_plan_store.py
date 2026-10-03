import json
import unittest
import tempfile
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.plan_store import save_preview, claim_preview
from src.models.schemas import AgentRunRequest
from src.models.settings import AgentPlanRecord
from src.models import settings
from src.routers import agent
from src.core.types import AgentImageAnalysis


class PlanApprovalTests(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.data_dir.cleanup)
        self.image_dir_patch = patch.object(settings, 'WORKSPACE_IMAGES_DIR', self.data_dir.name)
        self.image_dir_patch.start()
        self.addCleanup(self.image_dir_patch.stop)
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        SQLModel.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.request = AgentRunRequest(
            config={'analysis': {'host': 'https://example.com/v1', 'model': 'vision', 'key': 'secret'},
                    'edit': {'host': 'https://example.com/v1', 'model': 'image'}},
            content={'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC', 'content': '提亮'},
            approved=True,
        )
        self.plan = AgentPlan(goal='提亮', steps=[
            AgentPlanStep(id='edit', tool='apply_ai_edit', params={'edit_prompt': '提亮'}),
            AgentPlanStep(id='check', tool='validate_result', depends_on=['edit']),
        ])
        self.plan_id = save_preview(self.db, self.request, self.plan, {'summary': '暗部偏暗'})
        self.request.plan = {**self.plan.model_dump(), 'approval_id': self.plan_id}

    def test_approved_plan_is_server_owned_and_single_use(self):
        self.assertEqual(claim_preview(self.db, self.request, 'run-1'), self.plan)
        with self.assertRaisesRegex(ValueError, '已提交'):
            claim_preview(self.db, self.request, 'run-2')
        record = self.db.get(AgentPlanRecord, self.plan_id)
        self.assertEqual(record.run_id, 'run-1')
        self.assertNotIn('secret', record.model_dump_json())
        self.assertNotIn('base64', record.model_dump_json())

    def test_changed_context_or_plan_is_rejected_without_consuming_preview(self):
        for field in ['prompt', 'image', 'model', 'host', 'plan']:
            request = self.request.model_copy(deep=True)
            if field == 'prompt': request.content.content = '换背景'
            if field == 'image': request.content.image += 'x'
            if field == 'model': request.config.edit.model = 'other'
            if field == 'host': request.config.edit.host = 'https://other.example/v1'
            if field == 'plan': request.plan['steps'][0]['params']['edit_prompt'] = '换背景'
            with self.subTest(field=field), self.assertRaises(ValueError):
                claim_preview(self.db, request, 'tampered')
        self.assertEqual(claim_preview(self.db, self.request, 'valid'), self.plan)

    def test_expired_plan_is_rejected(self):
        record = self.db.get(AgentPlanRecord, self.plan_id)
        record.expires_at = 0
        self.db.add(record)
        self.db.commit()
        with self.assertRaisesRegex(ValueError, '过期'):
            claim_preview(self.db, self.request, 'late')

    def test_http_rejects_changed_prompt_before_model_call(self):
        app = FastAPI()
        app.include_router(agent.router)
        self.request.content.content = '换背景'
        with patch.object(agent, 'get_session', side_effect=lambda: Session(self.engine)), \
             patch.object(agent, 'run_agent', new_callable=AsyncMock) as run:
            with TestClient(app) as client:
                response = client.post('/api/v1/agent/run', json=self.request.model_dump())
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['detail']['code'], 'PLAN_APPROVAL_STALE')
            run.assert_not_called()

    def test_http_approved_run_and_replay(self):
        app = FastAPI()
        app.include_router(agent.router)
        analysis = AgentImageAnalysis('landscape', '风景', [], '暗部偏暗', '提亮')
        result = (analysis, '{}', [self.request.content.image], None, self.plan.model_dump(), {'runs': []})
        with patch.object(agent, 'get_session', side_effect=lambda: Session(self.engine)), \
             patch.object(agent, 'run_agent', new_callable=AsyncMock, return_value=result) as run:
            with TestClient(app) as client:
                response = client.post('/api/v1/agent/run', json=self.request.model_dump())
                self.assertEqual(response.status_code, 200)
                self.assertIn('"type": "result"', response.text)
                self.assertEqual(run.await_args.kwargs['planned_plan'], self.plan)
                replay = client.post('/api/v1/agent/run', json=self.request.model_dump())
                self.assertEqual(replay.status_code, 409)
            self.assertEqual(run.await_count, 1)

    def test_http_run_reuses_frozen_analysis_snapshot(self):
        app = FastAPI()
        app.include_router(agent.router)
        raw = json.dumps({
            'imageType': 'landscape',
            'imageTypeReason': '场景',
            'deficiencies': [],
            'summary': '已冻结分析',
            'editPrompt': '提亮',
        }, ensure_ascii=False)
        record = self.db.get(AgentPlanRecord, self.plan_id)
        record.analysis_raw_json = raw
        self.db.add(record)
        self.db.commit()
        analysis = AgentImageAnalysis('landscape', '场景', [], '已冻结分析', '提亮')
        result = (analysis, raw, [self.request.content.image], None, self.plan.model_dump(), {'runs': []})
        with patch.object(agent, 'get_session', side_effect=lambda: Session(self.engine)), \
             patch.object(agent, 'run_agent', new_callable=AsyncMock, return_value=result) as run:
            with TestClient(app) as client:
                response = client.post('/api/v1/agent/run', json=self.request.model_dump())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(run.await_args.kwargs['planned_analysis'], analysis)
            self.assertEqual(run.await_args.kwargs['planned_analysis_raw'], raw)
