import json
import os
import re
import urllib.error
import urllib.request

from gemma_utils import parse_json_output

DEFAULT_API_BASE = "http://localhost:8007/v1"
DEFAULT_API_KEY = "sk-local"
DEFAULT_MODEL = "Qwen/Qwen3.5-27B"

# Ports to scan when looking for a Qwen vLLM instance (story / director).
QWEN_PROBE_PORTS = (8007, 8001, 8002, 8004, 8006, 8009, 8008)

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


def _fetch_model_ids(api_base: str, *, timeout: float = 3.0) -> list[str]:
    models_url = f"{api_base.rstrip('/')}/models"
    with urllib.request.urlopen(models_url, timeout=timeout) as response:
        body = response.read(8192).decode("utf-8", errors="replace")
    payload = json.loads(body)
    return [entry.get("id", "") for entry in payload.get("data", []) if entry.get("id")]


def _is_qwen_model(model_id: str) -> bool:
    return "qwen" in model_id.lower()


def _pick_qwen_model(model_ids: list[str], preferred: str | None = None) -> str | None:
    if preferred and preferred in model_ids and _is_qwen_model(preferred):
        return preferred
    for mid in model_ids:
        if _is_qwen_model(mid):
            return mid
    return None


def discover_qwen_endpoint(*, preferred_model: str | None = None) -> tuple[str, str] | None:
    """Return (api_base, model_id) for the first reachable server that exposes Qwen."""
    preferred_model = normalize_model_id(preferred_model or os.environ.get("QWEN_MODEL", DEFAULT_MODEL))
    for port in QWEN_PROBE_PORTS:
        base = f"http://127.0.0.1:{port}/v1"
        try:
            ids = _fetch_model_ids(base)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            continue
        chosen = _pick_qwen_model(ids, preferred_model)
        if chosen:
            return base, chosen
    return None


def ensure_qwen_for_story_layout(*, strict: bool = True) -> None:
    """
    Point OPENAI_API_BASE / QWEN_MODEL at Qwen vLLM for director story layout.
    Does not use Sarvam or other non-Qwen servers when strict=True.
    """
    os.environ.setdefault("OPENAI_API_KEY", DEFAULT_API_KEY)
    preferred = normalize_model_id(os.environ.get("QWEN_MODEL", DEFAULT_MODEL))
    configured_base = os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE)

    def try_base(base: str) -> tuple[str, str] | None:
        try:
            ids = _fetch_model_ids(base)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None
        if strict and ids and not any(_is_qwen_model(i) for i in ids):
            return None
        chosen = _pick_qwen_model(ids, preferred)
        if chosen:
            return base, chosen
        return None

    hit = try_base(configured_base)
    if not hit:
        hit = discover_qwen_endpoint(preferred_model=preferred)

    if hit:
        base, model = hit
        os.environ["OPENAI_API_BASE"] = base
        os.environ["QWEN_MODEL"] = model
        if base != configured_base or model != preferred:
            print(f"Story layout LLM: Qwen {model!r} @ {base}")
        return

    raise SystemExit(
        "No Qwen vLLM found for story / director layout.\n"
        "Sarvam and Gemma are not used for directing — start Qwen first:\n\n"
        "  Terminal A:\n"
        "    bash scripts/start_qwen_vllm.sh\n\n"
        "  Terminal B:\n"
        "    export OPENAI_API_BASE=http://localhost:8007/v1\n"
        "    export QWEN_MODEL=Qwen/Qwen3.5-27B\n"
        "    curl -s $OPENAI_API_BASE/models | head\n"
        "    python3 scripts/run_textbook_director.py --book-id <id> --output-root output\n"
    )


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
            "Start Qwen vLLM (story layout requires Qwen, not Sarvam):\n"
            "  bash scripts/start_qwen_vllm.sh\n"
            "Then:\n"
            f"  export OPENAI_API_BASE={DEFAULT_API_BASE}\n"
            f"  export QWEN_MODEL={DEFAULT_MODEL}\n"
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

    if model_ids and not any(_is_qwen_model(i) for i in model_ids):
        raise SystemExit(
            f"Server at {api_base} has {model_ids} — no Qwen model.\n"
            "Director / story layout must use Qwen vLLM. Start: bash scripts/start_qwen_vllm.sh"
        )

    if model_ids and model not in model_ids:
        fallback = _pick_qwen_model(model_ids, model)
        if fallback:
            os.environ["QWEN_MODEL"] = fallback
            print(f"Using Qwen model {fallback!r} (server list: {model_ids})")
        else:
            print(
                f"Warning: model {model!r} not in server list {model_ids}. "
                "Set QWEN_MODEL to an available id or start the expected model."
            )


def _qwen_completion(
    client,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    raw_text = response.choices[0].message.content or ""
    return strip_thinking(raw_text)


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
    json_retries: int = 3,
) -> dict:
    from openai import OpenAI

    resolved_base = api_base or os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE)
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", DEFAULT_API_KEY)
    resolved_model = normalize_model_id(model or os.environ.get("QWEN_MODEL", DEFAULT_MODEL))

    verify_qwen_api(api_base=resolved_base, model=resolved_model)

    client = OpenAI(base_url=resolved_base, api_key=resolved_key)
    raw_text = _qwen_completion(
        client,
        model=resolved_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    last_error: ValueError | None = None
    for attempt in range(json_retries):
        try:
            return parse_json_output(raw_text, validate)
        except ValueError as exc:
            last_error = exc
            if attempt + 1 >= json_retries:
                break
            print(f"JSON parse failed ({exc}); retrying with repair pass ({attempt + 2}/{json_retries})...")
            fix_system = (
                "You output ONLY valid JSON — a single object. No markdown fences, no commentary. "
                "If the draft was truncated, shorten scene_table to fit while keeping syllabus accuracy."
            )
            fix_user = (
                f"Fix into valid complete JSON matching the original schema request.\n"
                f"Parse error: {exc}\n\n"
                f"Draft to repair (may be truncated):\n{raw_text[:60000]}"
            )
            raw_text = _qwen_completion(
                client,
                model=resolved_model,
                system_prompt=fix_system,
                user_prompt=fix_user,
                max_tokens=max_tokens,
                temperature=0.2,
            )

    raise last_error if last_error else ValueError("Model output is not valid JSON")
