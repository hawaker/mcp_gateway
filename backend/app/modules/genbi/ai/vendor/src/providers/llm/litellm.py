import logging
import os
from typing import Any, Callable, Dict, List, Optional

import backoff
import openai
from litellm import Router, acompletion

logger = logging.getLogger("wren-ai-service")

from src.core.provider import LLMProvider
from src.providers.llm import (
    ChatMessage,
    StreamingChunk,
    build_chunk,
    build_message,
    check_finish_reason,
    connect_chunks,
    convert_message_to_openai_format,
)
from src.providers.loader import provider
from src.utils import extract_braces_content, remove_trailing_slash

try:
    from src.genbi_llm_context import (
        downgrade_json_schema_kwargs,
        is_response_format_unavailable_error,
        merge_disable_thinking_kwargs,
        resolve_llm_call,
        sanitize_generation_kwargs,
        strip_assistant_content,
    )
except ImportError:

    def resolve_llm_call(model, api_key, api_base, model_kwargs):
        return model, api_key, api_base, dict(model_kwargs or {})

    def sanitize_generation_kwargs(model, kwargs):
        return dict(kwargs or {})

    def downgrade_json_schema_kwargs(model, kwargs):
        return dict(kwargs or {})

    def is_response_format_unavailable_error(exc):
        return False

    def merge_disable_thinking_kwargs(kwargs):
        return dict(kwargs or {})

    def strip_assistant_content(text):
        return text or ""


@provider("litellm_llm")
class LitellmLLMProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key_name: Optional[
            str
        ] = None,  # e.g. OPENAI_API_KEY, LLM_ANTHROPIC_API_KEY, etc.
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        timeout: float = 120.0,
        context_window_size: int = 100000,
        fallback_model_list: Optional[List[Dict[str, Any]]] = None,
        fallback_testing: bool = False,
        **_,
    ):
        self._model = model
        # Note: _api_key/_api_base/_api_version kept for vendor compat; litellm reads env directly.
        self._api_key = os.getenv(api_key_name) if api_key_name else None
        self._api_base = remove_trailing_slash(api_base) if api_base else None
        self._api_version = api_version
        self._model_kwargs = kwargs or {}
        self._timeout = timeout
        self._context_window_size = context_window_size
        # build a dynamic list of all fallback model names (beyond the first)
        self._has_fallbacks = (
            fallback_model_list is not None and len(fallback_model_list) > 1
        )
        fallbacks = (
            [{self._model: [m["model_name"] for m in fallback_model_list[1:]]}]
            if self._has_fallbacks
            else []
        )
        self._router = Router(
            model_list=fallback_model_list or [],
            fallbacks=fallbacks,
        )
        self._enable_fallback_testing = fallback_testing and self._has_fallbacks

    def get_model(self):
        try:
            from src.genbi_llm_context import current_credentials

            creds = current_credentials()
            if creds:
                return creds.text_litellm_model
        except ImportError:
            pass
        return self._model

    def get_generator(
        self,
        system_prompt: Optional[str] = None,
        generation_kwargs: Optional[Dict[str, Any]] = None,
        streaming_callback: Optional[Callable[[StreamingChunk], None]] = None,
    ):
        pipeline_generation_kwargs = generation_kwargs or {}

        @backoff.on_exception(backoff.expo, openai.APIError, max_time=60.0, max_tries=3)
        async def _run(
            prompt: str,
            image_url: Optional[str] = None,
            current_system_prompt: Optional[str] = None,
            history_messages: Optional[List[ChatMessage]] = None,
            generation_kwargs: Optional[Dict[str, Any]] = None,
            query_id: Optional[str] = None,
        ):
            message = ChatMessage.from_user(prompt, image_url)
            _system_prompt = system_prompt
            if current_system_prompt:
                _system_prompt = current_system_prompt

            if _system_prompt:
                messages = [ChatMessage.from_system(_system_prompt)]
                if history_messages:
                    messages.extend(history_messages)
                messages.append(message)
            else:
                if history_messages:
                    messages = history_messages + [message]
                else:
                    messages = [message]

            openai_formatted_messages = [
                convert_message_to_openai_format(message) for message in messages
            ]

            model, api_key, api_base, model_kwargs = resolve_llm_call(
                self._model,
                self._api_key,
                self._api_base,
                self._model_kwargs,
            )
            generation_kwargs = sanitize_generation_kwargs(
                model,
                {
                    **pipeline_generation_kwargs,
                    **model_kwargs,
                    **(generation_kwargs or {}),
                },
            )

            bare_model = (model or "").split("/", 1)[-1]
            allowed_openai_params = list(generation_kwargs.get("allowed_openai_params", []))
            if bare_model.startswith("gpt-5") and "reasoning_effort" not in allowed_openai_params:
                allowed_openai_params.append("reasoning_effort")

            async def _call_completion(call_kwargs: Dict[str, Any]):
                if self._has_fallbacks:
                    return await self._router.acompletion(
                        model=model,
                        messages=openai_formatted_messages,
                        stream=streaming_callback is not None,
                        allowed_openai_params=allowed_openai_params,
                        mock_testing_fallbacks=self._enable_fallback_testing,
                        **call_kwargs,
                    )
                return await acompletion(
                    model=model,
                    api_key=api_key,
                    api_base=api_base,
                    api_version=self._api_version,
                    timeout=self._timeout,
                    messages=openai_formatted_messages,
                    stream=streaming_callback is not None,
                    allowed_openai_params=allowed_openai_params,
                    **call_kwargs,
                )

            async def _complete(kwargs: Dict[str, Any]):
                # Same as graph_llm_clients: disable thinking per vendor; retry bare if rejected.
                with_disable = merge_disable_thinking_kwargs(kwargs)
                try:
                    return await _call_completion(with_disable)
                except Exception:
                    fallback = {k: v for k, v in kwargs.items() if k != "extra_body"}
                    return await _call_completion(fallback)

            try:
                completion = await _complete(generation_kwargs)
            except Exception as exc:
                rf = generation_kwargs.get("response_format")
                if not (
                    isinstance(rf, dict)
                    and rf.get("type") == "json_schema"
                    and is_response_format_unavailable_error(exc)
                ):
                    raise
                logger.warning(
                    "genbi litellm: model=%s rejected json_schema, retrying json_object",
                    model,
                )
                completion = await _complete(
                    downgrade_json_schema_kwargs(model, generation_kwargs)
                )

            completions: List[ChatMessage] = []
            if streaming_callback is not None:
                num_responses = generation_kwargs.pop("n", 1)
                if num_responses > 1:
                    raise ValueError(
                        "Cannot stream multiple responses, please set n=1."
                    )
                chunks: List[StreamingChunk] = []

                async for chunk in completion:
                    if chunk.choices and streaming_callback:
                        chunk_delta: StreamingChunk = build_chunk(chunk)
                        chunks.append(chunk_delta)
                        streaming_callback(
                            chunk_delta, query_id
                        )  # invoke callback with the chunk_delta
                completions = [connect_chunks(chunk, chunks)]
            else:
                completions = [
                    build_message(completion, choice) for choice in completion.choices
                ]

            # before returning, do post-processing of the completions
            for response in completions:
                check_finish_reason(response)

            return {
                "replies": [
                    extract_braces_content(strip_assistant_content(message.content))
                    for message in completions
                ],
                "meta": [message.meta for message in completions],
            }

        return _run
