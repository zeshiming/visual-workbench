from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ImageType = Literal["landscape", "portrait_with_people", "pure_portrait"]

DeficiencyCategory = Literal[
    "color", "clarity", "composition", "portrait_detail", "lighting", "other"
]

DeficiencySeverity = Literal["low", "medium", "high"]


@dataclass
class ImageDeficiency:
    category: DeficiencyCategory
    description: str
    severity: DeficiencySeverity


@dataclass
class AgentImageAnalysis:
    imageType: ImageType
    imageTypeReason: str
    deficiencies: list[ImageDeficiency]
    summary: str
    editPrompt: str

    def to_dict(self) -> dict:
        return {
            "imageType": self.imageType,
            "imageTypeReason": self.imageTypeReason,
            "deficiencies": [
                {"category": d.category, "description": d.description, "severity": d.severity}
                for d in self.deficiencies
            ],
            "summary": self.summary,
            "editPrompt": self.editPrompt,
        }
