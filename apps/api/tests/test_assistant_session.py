import asyncio
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine, select

from src.models.schemas import AssistantRequest, AssistantSessionCreate
from src.models.settings import AssistantMessageRecord
import src.routers.assistant as assistant_router


PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'


def test_assistant_session_persists_turns_and_uses_server_history():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    get_session = lambda: Session(engine)

    async def completion(**kwargs):
        text = kwargs['messages'][-1]['content'][1]['text']
        assert '上一轮问题' in text
        return {'text': '{"reply":"继续当前任务。","intent":"answer","action":"none"}', 'trace': {}}

    async def run():
        with patch.object(assistant_router, 'get_session', get_session), \
             patch.object(assistant_router, 'litellm_completion', new=completion):
            session = await assistant_router.create_session(AssistantSessionCreate(workspace_id='w'))
            request = AssistantRequest(
                config={'analysis': {'host': 'https://example.com/v1', 'key': 'x', 'model': 'a'}, 'edit': {'host': 'https://example.com/v1', 'key': 'x', 'model': 'e'}},
                content={'image': PIXEL, 'content': '上一轮问题'}, session_id=session['sessionId'], workspace_id='w',
            )
            result = await assistant_router.respond_to_assistant(request)
            assert result.session_id == session['sessionId']
            with Session(engine) as db:
                rows = db.exec(select(AssistantMessageRecord)).all()
                assert [row.role for row in rows] == ['user', 'assistant']
    asyncio.run(run())
