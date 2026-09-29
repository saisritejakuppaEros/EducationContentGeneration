import json
import re
from pathlib import Path


def load_prompt_template(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    system_marker = "# System\n"
    user_marker = "\n# User\n"
    if system_marker not in text or user_marker not in text:
        raise ValueError(f"Prompt file must contain '# System' and '# User' sections: {path}")
    system_part, user_part = text.split(user_marker, 1)
    system_prompt = system_part.removeprefix(system_marker).strip()
    user_template = user_part.strip()
    return system_prompt, user_template


def fill_user_prompt(template: str, **replacements: str) -> str:
    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{{{key}}}}}", value.strip())
    return result


def parse_response_text(processor, response: str, input_ids) -> str:
    parsed = processor.parse_response(response, prefix=input_ids)
    if isinstance(parsed, dict):
        for key in ("content", "text", "response", "final"):
            if key in parsed and parsed[key]:
                return str(parsed[key]).strip()
        if "messages" in parsed and parsed["messages"]:
            last = parsed["messages"][-1]
            if isinstance(last, dict) and last.get("content"):
                return str(last["content"]).strip()
    if isinstance(parsed, str):
        return parsed.strip()
    return response.strip()


def extract_json_text(raw: str) -> str:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        return fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def repair_json_string_escapes(json_text: str) -> str:
    """Fix invalid or ambiguous backslash escapes in JSON strings (common with LaTeX)."""
    out: list[str] = []
    in_string = False
    i = 0
    length = len(json_text)

    while i < length:
        ch = json_text[i]
        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        if ch == "\\":
            if i + 1 >= length:
                out.append("\\\\")
                i += 1
                continue
            nxt = json_text[i + 1]
            if nxt == "u":
                hex_part = json_text[i + 2 : i + 6]
                if len(hex_part) == 4 and all(c in "0123456789abcdefABCDEF" for c in hex_part):
                    out.append(json_text[i : i + 6])
                    i += 6
                    continue
                out.append("\\\\")
                out.append("u")
                i += 2
                continue
            if nxt.isalpha():
                j = i + 2
                while j < length and json_text[j].isalpha():
                    j += 1
                run = json_text[i + 1 : j]
                if len(run) == 1 and run in "bfnrt" and (j >= length or not json_text[j].isalpha()):
                    out.append("\\")
                    out.append(run)
                else:
                    out.append("\\\\")
                    out.append(run)
                i = j
                continue
            if nxt in '"\\/':
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            out.append("\\\\")
            out.append(nxt)
            i += 2
            continue

        out.append(ch)
        if ch == '"':
            in_string = False
        i += 1

    return "".join(out)


def parse_json_output(raw: str, validate) -> dict:
    json_text = extract_json_text(raw)
    last_exc: json.JSONDecodeError | None = None
    data = None
    for candidate in (json_text, repair_json_string_escapes(json_text)):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError as exc:
            last_exc = exc

    if data is None:
        raise ValueError(f"Model output is not valid JSON: {last_exc}") from last_exc

    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object")

    validate(data)
    return data


def load_gemma_model(model_path: Path):
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    processor = AutoProcessor.from_pretrained(str(model_path))
    model = AutoModelForMultimodalLM.from_pretrained(
        str(model_path),
        dtype="auto",
        device_map="auto",
    )
    return processor, model


def run_gemma_json_with_model(
    *,
    processor,
    model,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int,
    enable_thinking: bool,
    validate,
) -> dict:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    ).to(model.device)

    input_len = inputs["input_ids"].shape[-1]
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=1.0,
        top_p=0.95,
        top_k=64,
    )

    response = processor.decode(outputs[0][input_len:], skip_special_tokens=False)
    raw_text = parse_response_text(processor, response, inputs["input_ids"])
    return parse_json_output(raw_text, validate)


def run_gemma_json_generation(
    *,
    system_prompt: str,
    user_prompt: str,
    model_path: Path,
    max_new_tokens: int,
    enable_thinking: bool,
    validate,
) -> dict:
    processor, model = load_gemma_model(model_path)
    return run_gemma_json_with_model(
        processor=processor,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_new_tokens=max_new_tokens,
        enable_thinking=enable_thinking,
        validate=validate,
    )
