"""Map model_id + api_base to litellm model strings."""

from __future__ import annotations

from typing import Optional

_KNOWN_LITELLM_PREFIXES = (
    "openai/",
    "azure/",
    "anthropic/",
    "bedrock/",
    "vertex_ai/",
    "gemini/",
    "deepseek/",
    "aliyun/",
    "dashscope/",
    "openrouter/",
)


def to_litellm_model(model_id: str, api_base: Optional[str] = None) -> str:
    mid = (model_id or "").strip()
    if not mid:
        return mid
    if any(mid.startswith(p) for p in _KNOWN_LITELLM_PREFIXES):
        return mid
    lowered = mid.lower()
    if (api_base or "").strip() and not lowered.startswith(("gpt-", "o1", "o3", "o4")):
        return f"openai/{mid}"
    if lowered.startswith(("gpt-", "o1", "o3", "o4")):
        return mid
    if lowered.startswith("claude"):
        return f"anthropic/{mid}"
    if lowered.startswith("gemini"):
        return f"gemini/{mid}"
    return mid


def llm_generation_kwargs_for(
    model_id: str,
    *,
    max_output_tokens: int | None = None,
) -> dict:
    bare = (model_id or "").split("/", 1)[-1]
    limit = max_output_tokens or 8192
    if bare.startswith("gpt-5"):
        return {
            "max_completion_tokens": limit,
            "n": 1,
            "seed": 0,
            "reasoning_effort": "minimal",
        }
    return {"max_tokens": limit, "n": 1, "seed": 0, "temperature": 0}
