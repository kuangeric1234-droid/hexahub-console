"""
Unit tests for LLMClient.

Real API calls are not made — provider SDK calls are patched at the module level.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.llm.client import LLMClient, LLMProvider, LLMResponse


# ── Anthropic ─────────────────────────────────────────────────────────────────

async def test_anthropic_complete_returns_response():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Hello from Claude")]
    mock_message.usage.input_tokens  = 10
    mock_message.usage.output_tokens = 5

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        client   = LLMClient(provider=LLMProvider.ANTHROPIC, model="claude-sonnet-4-6")
        response = await client.complete("system", "user")

    assert isinstance(response, LLMResponse)
    assert response.content       == "Hello from Claude"
    assert response.provider      == LLMProvider.ANTHROPIC
    assert response.input_tokens  == 10
    assert response.output_tokens == 5


# ── OpenAI ────────────────────────────────────────────────────────────────────

async def test_openai_complete_returns_response():
    mock_choice  = MagicMock()
    mock_choice.message.content = "Hello from GPT"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens      = 20
    mock_response.usage.completion_tokens  = 10

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("openai.AsyncOpenAI", return_value=mock_openai):
        client   = LLMClient(provider=LLMProvider.OPENAI, model="gpt-4o")
        response = await client.complete("system", "user")

    assert response.content  == "Hello from GPT"
    assert response.provider == LLMProvider.OPENAI


# ── Provider routing ──────────────────────────────────────────────────────────

async def test_qwen_uses_openai_compat_with_correct_base_url():
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Qwen response"))],
            usage=MagicMock(prompt_tokens=5, completion_tokens=5),
        )
    )

    with patch("openai.AsyncOpenAI", return_value=mock_openai) as patched:
        client = LLMClient(provider=LLMProvider.QWEN)
        await client.complete("s", "u")

    call_kwargs = patched.call_args.kwargs
    assert "dashscope.aliyuncs.com" in call_kwargs.get("base_url", "")


async def test_unknown_provider_raises():
    client = LLMClient.__new__(LLMClient)
    client.provider = "nonexistent"  # type: ignore[assignment]
    client.model    = "x"
    with pytest.raises((ValueError, Exception)):
        await client.complete("s", "u")


# ── Model defaults ────────────────────────────────────────────────────────────

def test_default_model_anthropic():
    c = LLMClient()
    assert c.model == "claude-sonnet-4-6"


def test_custom_model_override():
    c = LLMClient(provider=LLMProvider.OPENAI, model="gpt-4o-mini")
    assert c.model == "gpt-4o-mini"
