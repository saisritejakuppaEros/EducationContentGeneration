import os
import re

from gemma_utils import parse_json_output

DEFAULT_API_BASE = "http://localhost:8000/v1"
DEFAULT_API_KEY = "sk-local"
DEFAULT_MODEL = "Qwen/Qwen3.5-27B"

_THINK_OPEN = "\x3cthink\x3e"
_THINK_CLOSE = "\x3c/think\x3e"
_THINK_BLOCK = re.compile(
    re.escape(_THINK_OPEN) + r"[\s\S]*?" + re.escape(_THINK_CLOSE),
    re.IGNORECASE,
)


def strip_thinking(text: str) -> str:
    cleaned = _THINK_BLOCK.sub("", text).strip()
    if cleaned.startswith("Thinking Process:"):
        brace = cleaned.find("{")
        if brace != -1:
            cleaned = cleaned[brace:]
    return cleaned.strip()


def normalize_model_id(model: str) -> str:
    """Strip LiteLLM provider prefix (openai/...) for direct vLLM OpenAI API calls."""
    if model.startswith("openai/"):
        return model.removeprefix("openai/")
    return model


def run_qwen_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int,
    temperature: float = 0.6,
    validate,
) -> dict:
    from openai import OpenAI

    resolved_base = api_base or os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE)
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", DEFAULT_API_KEY)
    resolved_model = normalize_model_id(model or os.environ.get("QWEN_MODEL", DEFAULT_MODEL))

    client = OpenAI(base_url=resolved_base, api_key=resolved_key)
    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    raw_text = response.choices[0].message.content or ""
    raw_text = strip_thinking(raw_text)
    return parse_json_output(raw_text, validate)
