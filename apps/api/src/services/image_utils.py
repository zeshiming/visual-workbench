"""Image processing utilities using Pillow."""

from __future__ import annotations

import base64
import io
import re

from PIL import Image, ImageDraw, ImageFilter


def decode_data_url(data_url: str) -> bytes:
    """Extract raw bytes from a base64 data URL."""
    match = re.match(r"^data:image/[^;]+;base64,(.+)$", data_url)
    if not match:
        raise ValueError("Invalid image data URL")
    return base64.b64decode(match.group(1))


def encode_as_data_url(image_data: bytes, fmt: str = "png") -> str:
    b64 = base64.b64encode(image_data).decode("ascii")
    return f"data:image/{fmt};base64,{b64}"


def read_image_dimensions_from_data_url(data_url: str) -> tuple[int, int]:
    raw = decode_data_url(data_url)
    img = Image.open(io.BytesIO(raw))
    return img.size  # (width, height)


def resize_image_to_max(data_url: str, max_dim: int = 2048) -> str:
    """Resize image so neither dimension exceeds max_dim."""
    raw = decode_data_url(data_url)
    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    if w <= max_dim and h <= max_dim:
        return data_url
    ratio = min(max_dim / w, max_dim / h)
    new_size = (int(w * ratio), int(h * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    fmt = img.format or "PNG"
    img.save(buf, format=fmt)
    return encode_as_data_url(buf.getvalue(), fmt.lower())


def compress_image_to_max_size(data_url: str, max_bytes: int = 3_500_000) -> str:
    """Reduce JPEG quality iteratively until image fits in max_bytes."""
    raw = decode_data_url(data_url)
    if len(raw) <= max_bytes:
        return data_url
    img = Image.open(io.BytesIO(raw))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    quality = 85
    while quality >= 10:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return encode_as_data_url(buf.getvalue(), "jpeg")
        quality -= 10
    return data_url


def prepare_image_for_api(data_url: str) -> str:
    """Resize and compress an image within API limits."""
    data_url = resize_image_to_max(data_url, max_dim=2048)
    data_url = compress_image_to_max_size(data_url, max_bytes=3_500_000)
    return data_url


def resize_image_to_dimensions(data_url: str, target_w: int, target_h: int) -> str:
    """Exact resize to given dimensions."""
    raw = decode_data_url(data_url)
    img = Image.open(io.BytesIO(raw))
    img = img.resize((target_w, target_h), Image.LANCZOS)
    buf = io.BytesIO()
    fmt = img.format or "PNG"
    img.save(buf, format=fmt)
    return encode_as_data_url(buf.getvalue(), fmt.lower())


def apply_editor_region_mask(source_data_url: str, output_data_url: str, marks: list[dict]) -> str:
    """Keep model pixels only inside the user-marked regions."""
    source = Image.open(io.BytesIO(decode_data_url(source_data_url))).convert("RGBA")
    output = Image.open(io.BytesIO(decode_data_url(output_data_url))).convert("RGBA")
    output = output.resize(source.size, Image.Resampling.LANCZOS)
    width, height = source.size
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    valid = 0
    for mark in marks:
        try:
            cx = float(mark["center_x"]) * width
            cy = float(mark["center_y"]) * height
            radius = max(1.0, float(mark["radius"]) * min(width, height))
        except (KeyError, TypeError, ValueError):
            continue
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
        valid += 1
    if not valid:
        raise ValueError("至少需要一个有效的局部编辑区域")
    feather = max(2, min(32, int(min(width, height) * 0.01)))
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    merged = Image.composite(output, source, mask)
    buffer = io.BytesIO()
    merged.save(buffer, format="PNG")
    return encode_as_data_url(buffer.getvalue(), "png")


def apply_basic_image_adjustments(data_url: str, adjustments: dict[str, float]) -> str:
    """Apply deterministic photo adjustments while preserving image dimensions.

    Values use the same -100..100 contract as the frontend renderer. The
    implementation intentionally uses the original pixel grid and writes PNG
    output so an Agent tool can safely chain another operation afterwards.
    """

    raw = decode_data_url(data_url)
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    pixels = image.load()
    width, height = image.size

    def value(name: str) -> float:
        try:
            parsed = float(adjustments.get(name, 0))
        except (TypeError, ValueError):
            return 0.0
        return max(-100.0, min(100.0, parsed))

    exposure_factor = 2 ** (value("exposure") / 100)
    contrast_value = value("contrast") * 2.55
    contrast_factor = (259 * (contrast_value + 255)) / (255 * (259 - contrast_value))
    saturation_factor = 1 + value("saturation") / 100
    temperature_shift = value("temperature") * 0.85
    tint_shift = value("tint") * 0.28
    highlights = value("highlights")
    shadows = value("shadows")

    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            red *= exposure_factor
            green *= exposure_factor
            blue *= exposure_factor

            red += temperature_shift - tint_shift * 0.35
            blue -= temperature_shift + tint_shift * 0.35
            green += tint_shift

            red = contrast_factor * (red - 128) + 128
            green = contrast_factor * (green - 128) + 128
            blue = contrast_factor * (blue - 128) + 128

            luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
            normalized_luminance = luminance / 255
            highlight_weight = max(0.0, (normalized_luminance - 0.5) * 2)
            shadow_weight = max(0.0, (0.5 - normalized_luminance) * 2)
            tonal_shift = (highlights * highlight_weight + shadows * shadow_weight) * 0.45
            red += tonal_shift
            green += tonal_shift
            blue += tonal_shift

            adjusted_luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
            red = adjusted_luminance + (red - adjusted_luminance) * saturation_factor
            green = adjusted_luminance + (green - adjusted_luminance) * saturation_factor
            blue = adjusted_luminance + (blue - adjusted_luminance) * saturation_factor

            pixels[x, y] = (
                max(0, min(255, round(red))),
                max(0, min(255, round(green))),
                max(0, min(255, round(blue))),
                alpha,
            )

    output = io.BytesIO()
    image.save(output, format="PNG")
    return encode_as_data_url(output.getvalue(), "png")


def estimate_auto_white_balance(data_url: str) -> dict[str, int]:
    """Estimate temperature and tint with a conservative gray-world sample."""

    image = Image.open(io.BytesIO(decode_data_url(data_url))).convert("RGBA")
    sample_width = min(image.width, 320)
    sample_height = max(1, round(image.height / max(image.width, 1) * sample_width))
    if (sample_width, sample_height) != image.size:
        image = image.resize((sample_width, sample_height), Image.Resampling.BILINEAR)

    red = green = blue = count = 0.0
    for r, g, b, alpha in image.getdata():
        luminance = r * 0.2126 + g * 0.7152 + b * 0.0722
        if alpha < 220 or luminance < 12 or luminance > 246:
            continue
        red += r
        green += g
        blue += b
        count += 1
    if not count:
        return {"temperature": 0, "tint": 0}

    average_red = red / count
    average_green = green / count
    average_blue = blue / count
    neutral = (average_red + average_green + average_blue) / 3

    def clamp(value: float) -> int:
        return max(-100, min(100, round(value)))

    return {
        "temperature": clamp((average_blue - average_red) * 0.8),
        "tint": clamp((neutral - average_green) * 0.8),
    }


def render_annotated_image(
    source_data_url: str,
    marks: list[dict],
) -> str:
    """Draw red numbered circles on the image for editor mode marking.

    Each mark should have: x, y, radius, label (number).
    Coordinates are relative to the image dimensions (0.0-1.0).
    """
    raw = decode_data_url(source_data_url)
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for mark in marks:
        cx = int(mark.get("x", 0.5) * w)
        cy = int(mark.get("y", 0.5) * h)
        r = int(mark.get("radius", 0.05) * min(w, h))
        label = str(mark.get("label", ""))

        # Draw red circle
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(255, 0, 0, 220),
            width=max(2, int(r * 0.08)),
        )
        # Draw label
        if label:
            # Simple number near the circle
            draw.text((cx + r + 4, cy - 8), label, fill=(255, 0, 0, 220))

    img = Image.alpha_composite(img, overlay)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return encode_as_data_url(out.getvalue(), "png")


async def fetch_image_as_data_url(url: str) -> str:
    """Fetch remote image URL and convert to base64 data URL."""
    if url.startswith("data:"):
        return url
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.get(url)
        response.raise_for_status()
        raw = response.content
        content_type = response.headers.get("content-type", "image/png")
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{content_type};base64,{b64}"
