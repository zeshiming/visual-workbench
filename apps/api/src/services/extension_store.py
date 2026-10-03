"""Durable storage for safe MCP/Skill metadata (never executable code or keys)."""

from __future__ import annotations

import json
import time

from ..mcp.registry import McpServerConfig
from ..models.settings import McpServerRecord, SkillRecord, get_session
from ..skills.registry import SkillManifest


def save_mcp_config(config: McpServerConfig) -> None:
    now = int(time.time() * 1000)
    with get_session() as db:
        record = db.get(McpServerRecord, config.id) or McpServerRecord(id=config.id, created_at=now)
        record.config_json = config.model_dump_json()
        record.updated_at = now
        db.add(record)
        db.commit()


def delete_mcp_config(server_id: str) -> None:
    with get_session() as db:
        record = db.get(McpServerRecord, server_id)
        if record:
            db.delete(record)
            db.commit()


def save_skill_manifest(manifest: SkillManifest) -> None:
    now = int(time.time() * 1000)
    with get_session() as db:
        record = db.get(SkillRecord, manifest.id) or SkillRecord(id=manifest.id, created_at=now)
        record.manifest_json = manifest.model_dump_json()
        record.updated_at = now
        db.add(record)
        db.commit()


def delete_skill_manifest(skill_id: str) -> None:
    with get_session() as db:
        record = db.get(SkillRecord, skill_id)
        if record:
            db.delete(record)
            db.commit()


def load_persisted_extensions() -> tuple[list[McpServerConfig], list[SkillManifest]]:
    servers: list[McpServerConfig] = []
    skills: list[SkillManifest] = []
    with get_session() as db:
        for record in db.query(McpServerRecord).all():
            try:
                servers.append(McpServerConfig.model_validate(json.loads(record.config_json)))
            except (ValueError, json.JSONDecodeError):
                continue
        for record in db.query(SkillRecord).all():
            try:
                skills.append(SkillManifest.model_validate(json.loads(record.manifest_json)))
            except (ValueError, json.JSONDecodeError):
                continue
    return servers, skills
