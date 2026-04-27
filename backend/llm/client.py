"""
Provider-agnostic LLM wrapper.

All agent code calls LLMClient.complete() — never a provider SDK directly.
Swap the provider per agent by passing a different LLMProvider at construction.

Supported providers
-------------------
anthropic  → Anthropic Claude (default)
openai     → OpenAI GPT
qwen       → Alibaba Cloud Qwen  (OpenAI-compatible endpoint)
deepseek   → DeepSeek            (OpenAI-compatible endpoint)
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

import structlog

from backend.config import settings

log = structlog.get_logger()


class LLMProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    QWEN      = "qwen"
    DEEPSEEK  = "deepseek"


_DEFAULT_MODELS: dict[LLMProvider, str] = {
    LLMProvider.ANTHROPIC: "claude-sonnet-4-6",
    LLMProvider.OPENAI:    "gpt-4o",
    LLMProvider.QWEN:      "qwen-max",
    LLMProvider.DEEPSEEK:  "deepseek-chat",
}

_BASE_URLS: dict[LLMProvider, str] = {
    LLMProvider.QWEN:     "https://dashscope.aliyuncs.com/compatible-mode/v1",
    LLMProvider.DEEPSEEK: "https://api.deepseek.com/v1",
}


@dataclass
class LLMResponse:
    content:       str
    provider:      LLMProvider
    model:         str
    input_tokens:  int
    output_tokens: int


class LLMClient:
    """
    Async LLM client.

    Usage::

        client   = LLMClient(provider=LLMProvider.ANTHROPIC)
        response = await client.complete(system_prompt, user_prompt)
        print(response.content)
    """

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model:    Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model    = model or _DEFAULT_MODELS[provider]

    async def complete(
        self,
        system_prompt: str,
        user_prompt:   str,
        max_tokens:    int   = 4096,
        temperature:   float = 0.7,
    ) -> LLMResponse:
        log.debug("llm_request", provider=self.provider.value, model=self.model)

        match self.provider:
            case LLMProvider.ANTHROPIC:
                return await self._call_anthropic(system_prompt, user_prompt, max_tokens, temperature)
            case LLMProvider.OPENAI | LLMProvider.QWEN | LLMProvider.DEEPSEEK:
                return await self._call_openai_compat(system_prompt, user_prompt, max_tokens, temperature)
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")

    # ── provider implementations ──────────────────────────────────────────────

    async def _call_anthropic(
        self,
        system_prompt: str,
        user_prompt:   str,
        max_tokens:    int,
        temperature:   float,
    ) -> LLMResponse:
        import anthropic  # lazy import keeps startup fast when not used

        client  = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return LLMResponse(
            content=message.content[0].text,
            provider=self.provider,
            model=self.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    async def _call_openai_compat(
        self,
        system_prompt: str,
        user_prompt:   str,
        max_tokens:    int,
        temperature:   float,
    ) -> LLMResponse:
        from openai import AsyncOpenAI  # lazy import

        kwargs: dict = {"api_key": self._api_key()}
        if base_url := _BASE_URLS.get(self.provider):
            kwargs["base_url"] = base_url

        client   = AsyncOpenAI(**kwargs)
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider=self.provider,
            model=self.model,
            input_tokens=usage.prompt_tokens     if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def _api_key(self) -> str:
        match self.provider:
            case LLMProvider.OPENAI:   return settings.OPENAI_API_KEY
            case LLMProvider.QWEN:     return settings.QWEN_API_KEY
            case LLMProvider.DEEPSEEK: return settings.DEEPSEEK_API_KEY
            case _:                    return ""
