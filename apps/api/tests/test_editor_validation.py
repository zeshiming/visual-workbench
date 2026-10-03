from unittest.mock import AsyncMock, patch
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers import editor


PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'


def test_editor_rejects_invalid_provider_output_before_frontend_receives_it():
    app = FastAPI()
    app.include_router(editor.router)
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    SQLModel.metadata.create_all(engine)
    request = {
        'config': {'edit': {'host': 'https://example.com/v1', 'key': 'x', 'model': 'image'}},
        'image': PIXEL, 'marks': [{'center_x': 0.5, 'center_y': 0.5, 'radius': 0.5}],
    }
    with patch.object(editor, 'get_session', side_effect=lambda: Session(engine)), \
         patch.object(editor, 'generate_image', new_callable=AsyncMock, return_value=(['data:image/png;base64,invalid'], None)):
        with TestClient(app) as client:
            response = client.post('/api/v1/editor/run', json=request)
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'EDITOR_OUTPUT_INVALID'
