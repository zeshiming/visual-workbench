"""Deterministic validation for AI-generated photo results."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, UnidentifiedImageError

from .image_utils import decode_data_url


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    metrics: dict[str, float | int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "issues": self.issues, "metrics": self.metrics}


def validate_image_result(
    source_data_url: str,
    output_data_url: str,
    *,
    require_same_size: bool = True,
) -> ValidationReport:
    issues: list[str] = []
    metrics: dict[str, float | int] = {}
    try:
        source_raw = decode_data_url(source_data_url)
        output_raw = decode_data_url(output_data_url)
        with Image.open(io.BytesIO(source_raw)) as source, Image.open(io.BytesIO(output_raw)) as output:
            source.load()
            output.load()
            metrics.update({
                "sourceWidth": source.width,
                "sourceHeight": source.height,
                "outputWidth": output.width,
                "outputHeight": output.height,
                "outputBytes": len(output_raw),
            })
            if require_same_size and source.size != output.size:
                issues.append(f"输出尺寸 {output.width}×{output.height} 与原图 {source.width}×{source.height} 不一致")
            sample = output.convert("RGB").resize((1, 1), Image.Resampling.BILINEAR)
            red, green, blue = sample.getpixel((0, 0))
            luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
            metrics["meanLuminance"] = round(luminance, 2)
            if luminance <= 1:
                issues.append("输出几乎全黑，可能是模型返回异常")
            elif luminance >= 254:
                issues.append("输出几乎全白，可能是模型返回异常")
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        issues.append(f"输出图片无法解码：{exc}")

    return ValidationReport(ok=not issues, issues=issues, metrics=metrics)
