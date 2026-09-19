import json
import os
import re
import urllib.error
import urllib.request

from gemma_utils import parse_json_output

DEFAULT_API_BASE = "http://localhost:8001/v1"
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


def verify_qwen_api(*, api_base: str, model: str) -> None:
    """Fail fast when the base URL is not an OpenAI-compatible vLLM server."""
    models_url = f"{api_base.rstrip('/')}/models"
    try:
        with urllib.request.urlopen(models_url, timeout=10) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Cannot reach Qwen/vLLM at {api_base}\n"
            f"  {exc}\n"
            "Start vLLM, then export:\n"
            f"  export OPENAI_API_BASE={api_base}\n"
            f"  export QWEN_MODEL={model}\n"
            "Verify: curl -s $OPENAI_API_BASE/models | head"
        ) from exc

    stripped = body.lstrip()
    if stripped.startswith("<!") or stripped.startswith("<html"):
        raise SystemExit(
            f"{api_base} returned HTML, not a vLLM OpenAI API.\n"
            "Port 8000 is often used by other apps (e.g. Daydream Scope).\n"
            "Start vLLM on a free port and point the pipeline at it:\n"
            "  vllm serve Qwen/Qwen3.5-27B --host 0.0.0.0 --port 8001 ...\n"
            "  export OPENAI_API_BASE=http://localhost:8001/v1\n"
            "  export QWEN_MODEL=Qwen/Qwen3.5-27B"
        )

    try:
        payload = json.loads(body)
        model_ids = [entry.get("id", "") for entry in payload.get("data", [])]
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{models_url} did not return JSON: {body[:200]!r}\n"
            "Check OPENAI_API_BASE ends with /v1 and points to vLLM."
        ) from exc

    if model_ids and model not in model_ids:
        print(
            f"Warning: model {model!r} not in server list {model_ids}. "
            "Set QWEN_MODEL to an available id or start the expected model."
        )


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

    verify_qwen_api(api_base=resolved_base, model=resolved_model)

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
