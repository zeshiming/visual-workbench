from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..models.settings import AppConfig, get_config, get_session

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    app_settings: str | None = None
    theme: str | None = None
    locale: str | None = None
    last_workspace: str | None = None


class SettingsResponse(BaseModel):
    app_settings: str
    theme: str
    locale: str
    last_workspace: str


def get_db() -> Session:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=SettingsResponse)
def load_settings(db: Session = Depends(get_db)) -> AppConfig:
    return get_config(db)


@router.put("", response_model=SettingsResponse)
def save_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
) -> AppConfig:
    config = get_config(db)
    if body.app_settings is not None:
        config.app_settings = body.app_settings
    if body.theme is not None:
        config.theme = body.theme
    if body.locale is not None:
        config.locale = body.locale
    if body.last_workspace is not None:
        config.last_workspace = body.last_workspace
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.delete("", response_model=SettingsResponse)
def clear_settings(db: Session = Depends(get_db)) -> AppConfig:
    """Reset all settings to defaults (one-click clear)."""
    config = get_config(db)
    config.app_settings = "{}"
    config.theme = "light"
    config.locale = "en"
    config.last_workspace = ""
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
