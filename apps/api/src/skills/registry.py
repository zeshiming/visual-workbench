"""Generic Skill registry; concrete Skills can be added later."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


MAX_SKILL_INSTRUCTIONS_CHARS = 64_000


class SkillManifest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1", max_length=32)
    description: str = Field(default="", max_length=2_000)
    instructions: str = Field(default="", max_length=MAX_SKILL_INSTRUCTIONS_CHARS)
    tools: list[str] = Field(default_factory=list, max_length=64)
    enabled: bool = True


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest] = {}

    def register(self, skill: SkillManifest) -> None:
        self._skills[skill.id] = skill

    def load_directory(self, root: str | Path) -> int:
        """Load manifests from child directories without executing Skill code."""

        directory = Path(root)
        loaded = 0
        if not directory.is_dir():
            return loaded
        for manifest_path in sorted(directory.glob("*/manifest.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                instructions_path = manifest_path.with_name("skill.md")
                if instructions_path.is_file():
                    instructions = instructions_path.read_text(encoding="utf-8")
                    if len(instructions) > MAX_SKILL_INSTRUCTIONS_CHARS:
                        continue
                    payload["instructions"] = instructions
                self.register(SkillManifest.model_validate(payload))
                loaded += 1
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return loaded

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._skills.get(skill_id)

    def remove(self, skill_id: str) -> bool:
        return self._skills.pop(skill_id, None) is not None

    def set_enabled(self, skill_id: str, enabled: bool) -> SkillManifest:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        updated = skill.model_copy(update={"enabled": enabled})
        self._skills[skill_id] = updated
        return updated

    def summaries(self) -> list[dict[str, str | list[str]]]:
        return [
            {"id": item.id, "name": item.name, "version": item.version, "description": item.description, "tools": item.tools}
            for item in self._skills.values()
            if item.enabled
        ]

    def planner_context(self, *, max_chars: int = 8_000) -> str:
        """Return bounded, non-executable Skill context for the planner."""
        chunks: list[str] = []
        for item in self._skills.values():
            if not item.enabled:
                continue
            chunk = f"- {item.id}@{item.version}: {item.description}; tools={','.join(item.tools)}"
            if item.instructions:
                chunk += f"\n  instructions: {item.instructions[:2_000]}"
            chunks.append(chunk)
        return "\n".join(chunks)[:max_chars]


skill_registry = SkillRegistry()
