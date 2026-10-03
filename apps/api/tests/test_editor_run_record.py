import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from fastapi import HTTPException

from src.models.schemas import EditorRunRequest
from src.models.settings import EditorRunRecord
import src.routers.editor as editor_router


PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'


def _request(run_id='run-1'):
    return EditorRunRequest(
        run_id=run_id, workspace_id='workspace-1', version_id='version-1',
        config={'edit': {'host': 'https://example.com/v1', 'key': 'x', 'model': 'image'}},
        image=PIXEL, marks=[{'center_x': .5, 'center_y': .5, 'radius': .5, 'description': '局部'}],
    )


def test_editor_run_record_is_completed_after_valid_output():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    SQLModel.metadata.create_all(engine)
    async def generate(**kwargs):
        kwargs['validation_sink'].update({'ok': True, 'metrics': {'outputWidth': 2, 'outputHeight': 2}})
        return [PIXEL], None

    async def run():
        with patch.object(editor_router, 'get_session', side_effect=lambda: Session(engine)), \
             patch.object(editor_router, 'generate_image', new=generate):
            response = await editor_router.handle_editor_run(_request())
            assert response.run_id == 'run-1'
    asyncio.run(run())
    with Session(engine) as db:
        record = db.get(EditorRunRecord, 'run-1')
        assert record.status == 'completed'
        assert record.workspace_id == 'workspace-1'
        assert record.input_version_id == 'version-1'
        assert 'outputWidth' in record.raw_validation_json


def test_editor_run_record_is_failed_when_provider_output_is_invalid():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    SQLModel.metadata.create_all(engine)
    async def run():
        with patch.object(editor_router, 'get_session', side_effect=lambda: Session(engine)), \
             patch.object(editor_router, 'generate_image', new_callable=AsyncMock, return_value=(['data:image/png;base64,invalid'], None)):
            try:
                await editor_router.handle_editor_run(_request('run-2'))
            except HTTPException as exc:
                assert exc.status_code == 502
            else:
                raise AssertionError('invalid editor output should be rejected')
    asyncio.run(run())
    with Session(engine) as db:
        assert db.get(EditorRunRecord, 'run-2').status == 'failed'
