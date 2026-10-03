"""JSON parsing and validation for agent analysis output.

Migrated from packages/agents/src/parse-analysis.ts
"""

from __future__ import annotations

import json
import logging

from .types import AgentImageAnalysis, ImageDeficiency

logger = logging.getLogger(__name__)


def strip_markdown_fence(text: str) -> str:
    """Remove markdown code fences from model output."""
    trimmed = text.strip()
    if not trimmed.startswith("```"):
        return trimmed
    return (
        trimmed.removeprefix("```json")
        .removeprefix("```")
        .strip()
        .removesuffix("```")
        .strip()
    )


def parse_agent_analysis(text: str) -> AgentImageAnalysis:
    """Parse the analysis model's JSON output into an AgentImageAnalysis.

    Raises ValueError if the JSON is missing required fields.
    """
    cleaned = strip_markdown_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse analysis JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Analysis output is not a JSON object")

    required = ["imageType", "imageTypeReason", "deficiencies", "summary", "editPrompt"]
    for field in required:
        if field not in parsed or (field == "editPrompt" and not str(parsed.get(field, "")).strip()):
            raise ValueError(f"Agent analysis JSON is missing required field: {field}")

    if not isinstance(parsed.get("deficiencies"), list):
        raise ValueError("Agent analysis JSON deficiencies is not an array")

    deficiencies = []
    for d in parsed["deficiencies"]:
        if isinstance(d, dict):
            deficiencies.append(
                ImageDeficiency(
                    category=d.get("category", "other"),
                    description=d.get("description", ""),
                    severity=d.get("severity", "low"),
                )
            )

    return AgentImageAnalysis(
        imageType=parsed["imageType"],
        imageTypeReason=parsed["imageTypeReason"],
        deficiencies=deficiencies,
        summary=parsed["summary"],
        editPrompt=parsed["editPrompt"],
    )
