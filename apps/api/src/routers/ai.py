"""Provider capability checks used by the model settings screen."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

from ..models.schemas import CapabilityCheckRequest, CapabilityCheckResponse

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _models_endpoint(host: str) -> str:
    base = host.rstrip("/")
    return f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"


def _infer_protocol(host: str, model: str) -> str:
    lowered_host = host.lower()
    lowered_model = model.lower()
    if lowered_model.startswith("qwen-image-3.0") or "maas.aliyuncs.com" in lowered_host:
        return "bailian-images-compatible"
    if "responses" in lowered_host or "mirror" in lowered_host:
        return "openai-responses-compatible"
    return "openai-compatible"


def _infer_capabilities(model: str, role: str) -> list[str]:
    lowered = model.lower()
    capabilities = ["text_output"]
    if role == "analysis" or any(token in lowered for token in ("vision", "vl", "astra", "gemini", "glm")):
        capabilities.append("image_input")
    if role == "edit" or any(token in lowered for token in ("image", "flux", "seedream")):
        capabilities.append("image_output")
    return capabilities


@router.post("/capabilities", response_model=CapabilityCheckResponse)
async def check_capabilities(request: CapabilityCheckRequest) -> CapabilityCheckResponse:
    protocol = _infer_protocol(request.host, request.model)
    capabilities = _infer_capabilities(request.model, request.role)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            response = await client.get(
                _models_endpoint(request.host),
                headers={"Authorization": f"Bearer {request.key}"} if request.key else {},
            )
        if response.status_code >= 400:
            return CapabilityCheckResponse(
                reachable=True,
                model_available=None,
                protocol=protocol,
                capabilities=capabilities,
                message=f"端点可访问，但认证或模型列表请求失败（HTTP {response.status_code}）。",
            )
        payload = response.json()
        model_ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
        available = request.model in model_ids if model_ids else None
        message = "模型已在端点列表中。" if available else "端点可访问；模型是否可用需要实际调用验证。"
        return CapabilityCheckResponse(
            reachable=True,
            model_available=available,
            protocol=protocol,
            capabilities=capabilities,
            message=message,
        )
    except httpx.TimeoutException:
        return CapabilityCheckResponse(
            reachable=False,
            protocol=protocol,
            capabilities=capabilities,
            message="连接超时。",
        )
    except Exception as exc:
        return CapabilityCheckResponse(
            reachable=False,
            protocol=protocol,
            capabilities=capabilities,
            message=f"连接失败：{exc}",
        )
