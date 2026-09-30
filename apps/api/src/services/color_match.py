"""Deterministic reference-image color matching."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image

from .image_utils import decode_data_url, encode_as_data_url


@dataclass(frozen=True)
class ChannelStats:
    mean: tuple[float, float, float]
    deviation: tuple[float, float, float]


def _channel_stats(image: Image.Image, max_dimension: int = 320) -> ChannelStats:
    sample = image.convert("RGBA")
    scale = min(1.0, max_dimension / max(sample.width, sample.height))
    if scale < 1:
        sample = sample.resize(
            (max(1, round(sample.width * scale)), max(1, round(sample.height * scale))),
            Image.Resampling.BILINEAR,
        )

    sums = [0.0, 0.0, 0.0]
    squares = [0.0, 0.0, 0.0]
    count = 0
    for red, green, blue, alpha in sample.getdata():
        if alpha < 20:
            continue
        for channel, value in enumerate((red, green, blue)):
            sums[channel] += value
            squares[channel] += value * value
        count += 1

    if not count:
        return ChannelStats(mean=(128.0, 128.0, 128.0), deviation=(1.0, 1.0, 1.0))

    mean = tuple(value / count for value in sums)
    deviation = tuple(
        math.sqrt(max(1.0, squares[index] / count - mean[index] ** 2))
        for index in range(3)
    )
    return ChannelStats(mean=mean, deviation=deviation)


def match_reference_color(target_data_url: str, reference_data_url: str) -> str:
    """Transfer reference RGB mean and deviation to the target image."""

    target = Image.open(io.BytesIO(decode_data_url(target_data_url))).convert("RGBA")
    reference = Image.open(io.BytesIO(decode_data_url(reference_data_url))).convert("RGBA")
    target_stats = _channel_stats(target)
    reference_stats = _channel_stats(reference)
    pixels = target.load()

    for y in range(target.height):
        for x in range(target.width):
            red, green, blue, alpha = pixels[x, y]
            output: list[int] = []
            for channel, value in enumerate((red, green, blue)):
                normalized = (value - target_stats.mean[channel]) / target_stats.deviation[channel]
                transferred = normalized * reference_stats.deviation[channel] + reference_stats.mean[channel]
                output.append(round(max(0.0, min(255.0, transferred))))
            pixels[x, y] = (*output, alpha)

    output = io.BytesIO()
    target.save(output, format="PNG")
    return encode_as_data_url(output.getvalue(), "png")
