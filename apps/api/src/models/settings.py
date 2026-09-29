from __future__ import annotations

import json
import os

from sqlmodel import Field, Session, SQLModel, create_engine

# ── Data directory (override via DOUSHABAO_DATA_DIR for Docker) ──
_DATA_DIR = os.environ.get("DOUSHABAO_DATA_DIR")
if _DATA_DIR:
    _db_path = os.path.join(_DATA_DIR, "doushabao.db")
    DATABASE_URL = f"sqlite:///{_db_path}"
    WORKSPACE_IMAGES_DIR = os.path.join(_DATA_DIR, "workspace_images")
else:
    DATABASE_URL = "sqlite:///./doushabao.db"
    WORKSPACE_IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspace_images")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class AppConfig(SQLModel, table=True):
    """Singleton table storing all app configuration (one row, always id=1)."""

    __tablename__ = "app_config"

    id: int = Field(default=1, primary_key=True)
    # JSON-serialized AppSettings (providers, models, defaultModelId, etc.)
    app_settings: str = Field(default="{}")
    theme: str = Field(default="light")
    locale: str = Field(default="en")
    last_workspace: str = Field(default="")


class WorkspaceRecord(SQLModel, table=True):
    """Saved workspace metadata (image data stored on filesystem)."""

    __tablename__ = "workspaces"

    id: str = Field(primary_key=True)
    title: str = Field(default="未命名")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)
    has_source_image: bool = Field(default=False)


def get_session() -> Session:
    return Session(engine)


def init_db() -> None:
    """Create tables and ensure the singleton row exists."""
    SQLModel.metadata.create_all(engine)
    os.makedirs(WORKSPACE_IMAGES_DIR, exist_ok=True)

    with Session(engine) as session:
        row = session.get(AppConfig, 1)
        if row is None:
            session.add(AppConfig())
            session.commit()


def get_config(session: Session) -> AppConfig:
    row = session.get(AppConfig, 1)
    if row is None:
        row = AppConfig()
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


# ── Workspace image file helpers ───────────────────────────────

def get_workspace_image_path(workspace_id: str) -> str:
    os.makedirs(WORKSPACE_IMAGES_DIR, exist_ok=True)
    return os.path.join(WORKSPACE_IMAGES_DIR, f"{workspace_id}.json")


def save_workspace_image_file(workspace_id: str, data_url: str | None) -> None:
    path = get_workspace_image_path(workspace_id)
    if data_url is None:
        if os.path.isfile(path):
            os.remove(path)
        return
    with open(path, "w") as f:
        json.dump({"dataUrl": data_url}, f)


def load_workspace_image_file(workspace_id: str) -> str | None:
    path = get_workspace_image_path(workspace_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
            return data.get("dataUrl")
    except (json.JSONDecodeError, KeyError):
        return None


def delete_workspace_image_file(workspace_id: str) -> None:
    save_workspace_image_file(workspace_id, None)
