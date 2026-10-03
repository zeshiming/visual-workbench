from __future__ import annotations

import json
import os
import time
import tempfile
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Field, Session, SQLModel, create_engine, select
from ..services.storage_migration import migrate_legacy_images

# ── Data directory (override via DOUSHABAO_DATA_DIR for Docker) ──
_DATA_DIR = os.environ.get("DOUSHABAO_DATA_DIR")
if _DATA_DIR:
    _db_path = os.path.join(_DATA_DIR, "doushabao.db")
    DATABASE_URL = f"sqlite:///{_db_path}"
    WORKSPACE_IMAGES_DIR = os.path.join(_DATA_DIR, "workspace_images")
else:
    # Resolve local data relative to the API package, not the process cwd.
    # The desktop launcher and `uv run` can start from different directories;
    # a cwd-relative SQLite URL otherwise causes startup to fail or creates
    # multiple databases depending on how the app was launched.
    _LOCAL_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DATABASE_URL = f"sqlite:///{os.path.join(_LOCAL_DATA_DIR, 'doushabao.db')}"
    WORKSPACE_IMAGES_DIR = os.path.join(_LOCAL_DATA_DIR, "workspace_images")

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
    current_version_id: str | None = Field(default=None, index=True)


class WorkspaceImagePointer(SQLModel, table=True):
    __tablename__ = "workspace_image_pointers"
    workspace_id: str = Field(primary_key=True)
    artifact_id: str | None = None


class WorkspaceVersionRecord(SQLModel, table=True):
    __tablename__ = "workspace_versions"
    id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    parent_id: str | None = Field(default=None, index=True)
    artifact_id: str | None = None
    asset_id: str | None = Field(default=None, index=True)
    operation: str = "commit"
    created_at: int = 0


class AssetRecord(SQLModel, table=True):
    """An image in a workspace's reusable asset library."""

    __tablename__ = "assets"

    id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    filename: str
    media_type: str
    kind: str = Field(default="import")
    feedback_id: str | None = Field(default=None, index=True)
    created_at: int
    size_bytes: int


class FeedbackRecord(SQLModel, table=True):
    __tablename__ = "feedback_records"
    id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    feedback_id: str = Field(index=True)
    customer_id: str = Field(default="")
    message: str = Field(default="")
    status: str = Field(default="open", index=True)
    created_at: int = 0
    updated_at: int = 0


class BatchJobRecord(SQLModel, table=True):
    """Persistent state for local batch processing jobs."""

    __tablename__ = "batch_jobs"

    id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    request_json: str = Field(default="{}")
    status: str = Field(default="queued", index=True)
    total: int = Field(default=0)
    processed: int = Field(default=0)
    processed_asset_ids_json: str = Field(default="[]")
    failure_ids_json: str = Field(default="[]")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class AgentPlanRecord(SQLModel, table=True):
    """Server-owned preview, bound to input and consumed once on approval."""

    __tablename__ = "agent_plans"
    id: str = Field(primary_key=True)
    context_hash: str
    plan_json: str
    analysis_json: str = "{}"
    analysis_raw_json: str = ""
    created_at: int
    expires_at: int
    approved_at: int = 0
    run_id: str = ""


class AgentRunRecord(SQLModel, table=True):
    """Durable state and trace summary for one single-image Agent run."""

    __tablename__ = "agent_runs"

    id: str = Field(primary_key=True)
    status: str = Field(default="created", index=True)
    request_summary_json: str = Field(default="{}")
    plan_json: str = Field(default="{}")
    trace_json: str = Field(default="{}")
    error: str = Field(default="")
    result_path: str = Field(default="")
    lease_owner: str = Field(default="")
    lease_expires_at: int = Field(default=0)
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class McpServerRecord(SQLModel, table=True):
    __tablename__ = "mcp_servers"
    id: str = Field(primary_key=True)
    config_json: str = Field(default="{}")
    created_at: int = 0
    updated_at: int = 0


class SkillRecord(SQLModel, table=True):
    __tablename__ = "skills"
    id: str = Field(primary_key=True)
    manifest_json: str = Field(default="{}")
    created_at: int = 0
    updated_at: int = 0


class AssistantSessionRecord(SQLModel, table=True):
    __tablename__ = "assistant_sessions"
    id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    asset_id: str = Field(default="")
    current_version: str = Field(default="current")
    status: str = Field(default="active", index=True)
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class AssistantMessageRecord(SQLModel, table=True):
    __tablename__ = "assistant_messages"
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    role: str
    content: str
    intent: str = Field(default="")
    action: str = Field(default="")
    suggested_prompt: str = Field(default="")
    version: str = Field(default="current")
    created_at: int = Field(default=0)


class EditorRunRecord(SQLModel, table=True):
    __tablename__ = "editor_runs"
    id: str = Field(primary_key=True)
    workspace_id: str = Field(default="", index=True)
    input_version_id: str = Field(default="")
    asset_id: str = Field(default="")
    output_version_id: str = Field(default="")
    status: str = Field(default="running", index=True)
    validation_json: str = Field(default="{}")
    raw_validation_json: str = Field(default="{}")
    error: str = Field(default="")
    created_at: int = 0
    updated_at: int = 0


class AgentStepRecord(SQLModel, table=True):
    """Durable step-level audit record for an Agent run."""

    __tablename__ = "agent_steps"

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    step_id: str
    tool: str
    status: str
    attempt: int = Field(default=1)
    output_json: str = Field(default="{}")
    output_artifact_path: str = Field(default="")
    error: str = Field(default="")
    started_at: int = Field(default=0)
    ended_at: int = Field(default=0)


class AgentEventRecord(SQLModel, table=True):
    __tablename__ = "agent_events"
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    sequence: int = Field(default=0, index=True)
    event_type: str
    status: str
    payload_json: str = "{}"
    created_at: int = 0


def get_session() -> Session:
    return Session(engine)


def _migrate_local_schema() -> None:
    """Apply additive SQLite migrations for databases created by older builds."""

    inspector = inspect(engine)
    if "agent_runs" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("agent_runs")}
        if "request_summary_json" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE agent_runs ADD COLUMN request_summary_json VARCHAR NOT NULL DEFAULT '{}'",
                )
    if "workspaces" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("workspaces")}
        if "current_version_id" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE workspaces ADD COLUMN current_version_id VARCHAR")
    for table, column in (("agent_plans", "analysis_raw_json"),
                          ("assets", "feedback_id"),
                          ("workspace_versions", "asset_id"), ("editor_runs", "asset_id"),
                          ("editor_runs", "output_version_id"), ("editor_runs", "raw_validation_json"),
                          ("agent_runs", "result_path"), ("agent_runs", "lease_owner"),
                          ("agent_steps", "output_artifact_path")):
        if table in inspector.get_table_names():
            columns = {item["name"] for item in inspector.get_columns(table)}
            if column not in columns:
                with engine.begin() as connection:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR NOT NULL DEFAULT ''")
    if "agent_runs" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("agent_runs")}
        if "lease_expires_at" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE agent_runs ADD COLUMN lease_expires_at INTEGER NOT NULL DEFAULT 0")
    if "agent_events" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("agent_events")}
        if "sequence" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE agent_events ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    """Create tables and ensure the singleton row exists."""
    if _DATA_DIR:
        os.makedirs(_DATA_DIR, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _migrate_local_schema()
    os.makedirs(WORKSPACE_IMAGES_DIR, exist_ok=True)

    if not _DATA_DIR:
        migrate_legacy_images(
            Path(__file__).resolve().parents[1] / 'workspace_images',
            Path(WORKSPACE_IMAGES_DIR),
        )

    with Session(engine) as session:
        row = session.get(AppConfig, 1)
        if row is None:
            session.add(AppConfig())
            session.commit()
        interrupted = session.exec(
            select(BatchJobRecord).where(
                BatchJobRecord.status.in_(["queued", "running", "paused", "cancelling"]),
            ),
        ).all()
        for job in interrupted:
            job.status = "interrupted"
            job.updated_at = int(time.time() * 1000)
        if interrupted:
            session.commit()
        agent_interrupted = session.exec(
            select(AgentRunRecord).where(
                AgentRunRecord.status.in_(["running", "paused", "cancelling"]),
            ),
        ).all()
        for run in agent_interrupted:
            run.status = "interrupted"
            run.lease_owner = ""
            run.lease_expires_at = 0
            run.updated_at = int(time.time() * 1000)
        if agent_interrupted:
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
    temporary = None
    try:
        # Write beside the destination so replacement is atomic on its filesystem.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=WORKSPACE_IMAGES_DIR,
                                         prefix=".workspace-", suffix=".tmp", delete=False) as f:
            temporary = f.name
            json.dump({"dataUrl": data_url}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)


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


def save_agent_result_file(run_id: str, payload: dict) -> str:
    directory = os.path.join(WORKSPACE_IMAGES_DIR, "agent_runs")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{run_id}.json")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=f".{run_id}-", suffix=".tmp", delete=False) as output:
            temporary = output.name
            json.dump(payload, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        return path
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def load_agent_result_file(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as source:
            value = json.load(source)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_agent_step_file(run_id: str, attempt: int, step_id: str, image: str) -> str:
    safe_step = ''.join(char if char.isalnum() or char in '-_' else '_' for char in step_id)
    directory = os.path.join(WORKSPACE_IMAGES_DIR, 'agent_runs', run_id, 'steps')
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f'{attempt}-{safe_step}.json')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as output:
            temporary = output.name
            json.dump({'dataUrl': image}, output, ensure_ascii=False)
            output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
        return path
    finally:
        if temporary and os.path.exists(temporary): os.remove(temporary)


def load_agent_step_file(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8') as source:
            value = json.load(source)
        image = value.get('dataUrl') if isinstance(value, dict) else None
        return image if isinstance(image, str) and image.startswith('data:image/') else None
    except (OSError, json.JSONDecodeError):
        return None
