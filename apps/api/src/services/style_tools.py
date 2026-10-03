"""Deterministic style presets and .cube LUT processing."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from .image_utils import apply_basic_image_adjustments, decode_data_url, encode_as_data_url


@dataclass(frozen=True)
class CubeLut:
    size: int
    values: tuple[float, ...]


STYLE_PRESETS: dict[str, dict[str, float]] = {
    "natural": {},
    "warm-film": {
        "contrast": 8, "highlights": -12, "shadows": 8,
        "saturation": 8, "temperature": 24, "tint": 4,
    },
    "cool-cinema": {
        "exposure": -4, "contrast": 12, "highlights": -20,
        "shadows": 8, "saturation": -5, "temperature": -22, "tint": -4,
    },
    "soft-portrait": {
        "exposure": 6, "contrast": -8, "highlights": -18,
        "shadows": 16, "saturation": -8, "temperature": 10, "tint": 2,
    },
}


def parse_cube_lut(contents: str) -> CubeLut:
    size = 0
    values: list[float] = []
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0].upper() == "LUT_3D_SIZE" and len(parts) == 2:
            size = int(parts[1])
            continue
        if len(parts) == 3:
            try:
                values.extend(float(part) for part in parts)
            except ValueError:
                continue

    expected = size ** 3 * 3
    if size < 2 or expected != len(values):
        raise ValueError("LUT 文件格式无效：需要完整的 LUT_3D_SIZE 数据")
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("LUT 输出值必须位于 0 到 1 之间")
    return CubeLut(size=size, values=tuple(values))


def apply_cube_lut(data_url: str, lut: CubeLut) -> str:
    image = Image.open(io.BytesIO(decode_data_url(data_url))).convert("RGBA")
    pixels = image.load()
    size = lut.size

    def sample(red: int, green: int, blue: int, channel: int) -> float:
        index = (red + size * (green + size * blue)) * 3 + channel
        return lut.values[index]

    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            position = [channel / 255 * (size - 1) for channel in (red, green, blue)]
            low = [int(value) for value in position]
            high = [min(size - 1, value + 1) for value in low]
            fraction = [position[index] - low[index] for index in range(3)]
            output: list[int] = []
            for channel in range(3):
                c000 = sample(low[0], low[1], low[2], channel)
                c100 = sample(high[0], low[1], low[2], channel)
                c010 = sample(low[0], high[1], low[2], channel)
                c110 = sample(high[0], high[1], low[2], channel)
                c001 = sample(low[0], low[1], high[2], channel)
                c101 = sample(high[0], low[1], high[2], channel)
                c011 = sample(low[0], high[1], high[2], channel)
                c111 = sample(high[0], high[1], high[2], channel)
                c00 = c000 + (c100 - c000) * fraction[0]
                c10 = c010 + (c110 - c010) * fraction[0]
                c01 = c001 + (c101 - c001) * fraction[0]
                c11 = c011 + (c111 - c011) * fraction[0]
                c0 = c00 + (c10 - c00) * fraction[1]
                c1 = c01 + (c11 - c01) * fraction[1]
                output.append(round(max(0, min(1, c0 + (c1 - c0) * fraction[2])) * 255))
            pixels[x, y] = (*output, alpha)

    output = io.BytesIO()
    image.save(output, format="PNG")
    return encode_as_data_url(output.getvalue(), "png")


def apply_style(data_url: str, *, style_id: str | None = None, lut_contents: str | None = None) -> str:
    """Apply a built-in style or an inline .cube LUT."""

    if style_id is not None:
        try:
            adjustments = STYLE_PRESETS[style_id]
        except KeyError as exc:
            raise ValueError(f"未知风格预设: {style_id}") from exc
        return apply_basic_image_adjustments(data_url, adjustments)
    if lut_contents:
        return apply_cube_lut(data_url, parse_cube_lut(lut_contents))
    raise ValueError("风格工具需要 style_id 或 lut_contents")
