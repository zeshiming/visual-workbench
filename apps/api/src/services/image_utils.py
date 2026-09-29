"""Image processing utilities using Pillow."""

from __future__ import annotations

import base64
import io
import re

from PIL import Image, ImageDraw


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
