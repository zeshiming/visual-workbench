"""AI provider client using litellm.

Replaces the previous hand-written httpx OpenRouter client.
litellm handles: provider routing, modality negotiation, retry, fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((data:image/[^)]+|https?://[^)\s]+)\)")


def _read_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _image_value(value: Any, mime_type: str = "image/png") -> list[str]:
    """Extract image URLs/data URLs from common OpenAI-compatible shapes."""
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("data:image/") or text.startswith("https://") or text.startswith("http://"):
            return [text]
        return _MARKDOWN_IMAGE_RE.findall(text)

    if isinstance(value, (list, tuple)):
        images: list[str] = []
        for item in value:
            images.extend(_image_value(item, mime_type))
        return images

    if isinstance(value, dict):
        b64 = value.get("b64_json") or value.get("base64")
        if isinstance(b64, str) and b64:
            return [f"data:{value.get('mime_type', mime_type)};base64,{b64}"]

        images: list[str] = []
        for key in ("image_url", "url", "image", "images", "content", "data"):
            if key in value:
                images.extend(_image_value(value[key], value.get("mime_type", mime_type)))
        return images

    # LiteLLM may expose response parts as typed objects rather than dicts.
    object_b64 = getattr(value, "b64_json", None) or getattr(value, "base64", None)
    if isinstance(object_b64, str) and object_b64:
        object_mime = getattr(value, "mime_type", mime_type)
        return [f"data:{object_mime};base64,{object_b64}"]

    for key in ("image_url", "url", "image", "images", "content", "data"):
        nested = getattr(value, key, None)
        if nested is not None:
            images = _image_value(nested, getattr(value, "mime_type", mime_type))
            if images:
                return images

    return []


def _text_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "\n".join(chunks) or None
    return None

# ── Lazy litellm import ───────────────────────────────────────
# litellm triggers heavy sub-imports (e.g. compression) that can crash
# in PyInstaller builds.  We defer the import until first actual use.
_litellm: Any = None


def _get_litellm():
    global _litellm
    if _litellm is None:
        try:
            import litellm  # type: ignore[import-untyped]

            _litellm = litellm
            # Suppress noisy startup warnings
            litellm.set_verbose = False  # pyright: ignore[reportAttributeAccessIssue]
            logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        except ImportError:
            raise RuntimeError(
                "litellm is not installed or failed to import. "
                "Run: uv sync --directory apps/api"
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize litellm: {exc}. "
                "The app will start but AI features will be unavailable."
            ) from exc
    return _litellm


# ── Provider detection ─────────────────────────────────────────

_OPENROUTER_PATTERNS = ["openrouter.ai"]
_GEMINI_PATTERNS = ["generativelanguage.googleapis.com", "googleapis.com"]
_KEY_MAP: dict[str, str] = {
    "openrouter": "openrouter_api_key",
    "gemini": "gemini_api_key",
}


def _detect_provider(host: str) -> str:
    """Detect provider kind from host URL."""
    h = host.lower()
    for pattern in _OPENROUTER_PATTERNS:
        if pattern in h:
            return "openrouter"
    for pattern in _GEMINI_PATTERNS:
        if pattern in h:
            return "gemini"
    return "openai-compatible"


def _resolve_api_key(provider: str, key: str) -> str:
    """Use provided key, or fall back to env-configured key."""
    if key:
        return key
    env_key = _KEY_MAP.get(provider)
    if env_key:
        val = getattr(settings, env_key, "")
        if val:
            return val
    return ""


def _build_litellm_params(
    host: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """Build litellm-compatible parameters from user config."""
    provider = _detect_provider(host)
    resolved_key = _resolve_api_key(provider, api_key)

    if not resolved_key:
        raise ValueError("API key is required. Configure it in settings or pass it in the request.")

    # litellm uses model prefixes for routing: openrouter/, gemini/, openai/
    if provider == "openrouter":
        litellm_model = f"openrouter/{model}"
        params: dict[str, Any] = {
            "model": litellm_model,
            "api_key": resolved_key,
        }
    elif provider == "gemini":
        litellm_model = f"gemini/{model}"
        params = {
            "model": litellm_model,
            "api_key": resolved_key,
        }
    else:
        # OpenAI-compatible
        litellm_model = f"openai/{model}"
        # Ensure host ends with /v1 for litellm
        api_base = host.rstrip("/")
        if not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"
        params = {
            "model": litellm_model,
            "api_key": resolved_key,
            "api_base": api_base,
        }

    return params


# ── Public API ─────────────────────────────────────────────────


async def litellm_completion(
    *,
    host: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Text completion via litellm (for analysis phase)."""
    litellm = _get_litellm()
    params = _build_litellm_params(host, api_key, model)
    response = await litellm.acompletion(
        **params,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=4096,
    )
    choice = response.choices[0]
    text = None
    if hasattr(choice, "message") and choice.message:
        if isinstance(choice.message.content, str):
            text = choice.message.content
    return {"text": text or ""}


async def litellm_image_completion(
    *,
    host: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    image_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Image-generating completion via litellm (for edit phase).

    Tries with modalities=["image", "text"] first; falls back to no modalities.
    """
    litellm = _get_litellm()
    params = _build_litellm_params(host, api_key, model)
    litellm_params = {
        **params,
        "messages": messages,  # type: ignore[arg-type]
    }

    if image_config:
        litellm_params["image_config"] = image_config

    # Try with image output modalities
    modalities_to_try: list[list[str] | None] = [["image", "text"], ["image"], None]

    last_error: Exception | None = None
    for modalities in modalities_to_try:
        try:
            if modalities is not None:
                litellm_params["modalities"] = modalities
            else:
                litellm_params.pop("modalities", None)

            response = await litellm.acompletion(**litellm_params)
            choice = response.choices[0]

            # Extract images from response
            images: list[str] = []
            text: str | None = None

            if hasattr(choice, "message") and choice.message:
                msg = choice.message
                # Providers place generated images in different OpenAI-compatible
                # fields: message.images, content parts, image_url, or data[].
                images.extend(_image_value(_read_value(msg, "images")))
                images.extend(_image_value(_read_value(msg, "content")))

                # Extract text content without treating it as an image response.
                text = _text_value(_read_value(msg, "content"))

            # Some gateways return the image-generation shape at response.data
            # instead of choices[0].message.images.
            images.extend(_image_value(_read_value(response, "data")))

            if images:
                return {"images": images, "text": text}

            last_error = RuntimeError("No images in response")

        except Exception as exc:
            last_error = exc
            logger.debug("Modality %s failed: %s", modalities, exc)
            continue

    raise last_error or RuntimeError("Image generation failed")
