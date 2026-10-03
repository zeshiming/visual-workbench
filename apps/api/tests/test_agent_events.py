import asyncio
import json
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine, select

import src.routers.agent as agent_router
from src.models.settings import AgentEventRecord, AgentRunRecord


def test_agent_state_events_are_durable_and_ordered():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
        agent_router._persist_agent_run('run-events', status='running')
        agent_router._persist_agent_run('run-events', status='paused')
        agent_router._persist_agent_run('run-events', status='failed', error='test')
    with Session(engine) as db:
        events = db.query(AgentEventRecord).filter(AgentEventRecord.run_id == 'run-events').order_by(AgentEventRecord.created_at).all()
        assert [event.status for event in events] == ['running', 'paused', 'failed']
        assert [event.sequence for event in events] == [1, 2, 3]
        assert json.loads(events[-1].payload_json)['error'] == 'test'
        assert db.get(AgentRunRecord, 'run-events').status == 'failed'


def test_agent_result_is_saved_outside_database_and_readable():
    import tempfile
    from pathlib import Path
    from src.models import settings
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(settings, 'WORKSPACE_IMAGES_DIR', directory):
            engine = create_engine('sqlite://')
            SQLModel.metadata.create_all(engine)
            with patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
                agent_router._persist_agent_run('result-run', status='running')
                agent_router._persist_agent_run('result-run', status='completed', result={'images': ['data:image/png;base64,x']})
            with Session(engine) as db:
                record = db.get(AgentRunRecord, 'result-run')
                assert Path(record.result_path).is_file()


def test_interrupted_run_reconcile_requires_review_without_replay():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
        agent_router._persist_agent_run('interrupted-run', status='interrupted', plan={'steps': []})
        response = asyncio.run(agent_router.reconcile_agent_run('interrupted-run'))
        assert response['status'] == 'needs_review'
        assert response['replayed'] is False
    with Session(engine) as db:
        record = db.get(AgentRunRecord, 'interrupted-run')
        assert record.status == 'needs_review'
        events = db.exec(select(AgentEventRecord).where(AgentEventRecord.run_id == 'interrupted-run')).all()
        assert any(event.status == 'needs_review' for event in events)


def test_stream_events_get_durable_sequences():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with patch.object(agent_router, 'get_session', side_effect=lambda: Session(engine)):
        agent_router._persist_agent_run('stream-run', status='running')
        first = agent_router._persist_agent_event(
            'stream-run', event_type='progress', status='analysis', payload={'phase': 'analysis'},
        )
        second = agent_router._persist_agent_event(
            'stream-run', event_type='tool', status='executed', payload={'stepId': 'balance'},
        )
    assert (first, second) == (2, 3)
