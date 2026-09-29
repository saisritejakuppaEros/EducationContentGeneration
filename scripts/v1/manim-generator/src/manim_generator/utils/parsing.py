import ast
import re


_MANIM_COMPAT_REPLACEMENTS = (
    (re.compile(r"\bCYAN\b"), "TEAL"),
    (re.compile(r",\s*glow_factor\s*=\s*[^,\)]+"), ""),
    (re.compile(r"glow_factor\s*=\s*[^,\)]+,\s*"), ""),
)


class SceneParsingError(Exception):
    """Exception raised when scene class names cannot be extracted from code."""

    pass


def apply_manim_compat_fixes(code: str) -> str:
    """Apply small, safe fixes for common invalid Manim Community API usage."""
    fixed = code
    for pattern, replacement in _MANIM_COMPAT_REPLACEMENTS:
        fixed = pattern.sub(replacement, fixed)
    return fixed


def truncate_trailing_prose(code: str) -> str:
    """Drop trailing non-Python prose sometimes appended after valid Manim code."""
    lines = code.splitlines()
    while lines:
        candidate = "\n".join(lines).strip()
        if not candidate:
            lines.pop()
            continue
        try:
            ast.parse(candidate)
            return candidate
        except SyntaxError:
            lines.pop()
    return code.strip()


def sanitize_manim_code(code: str) -> str:
    """Normalize extracted LLM code before execution."""
    cleaned = truncate_trailing_prose(code.strip())
    return apply_manim_compat_fixes(cleaned)


def parse_code_block(text: str) -> str:
    """
    Extract Python source from an LLM response.

    Handles closed/unclosed markdown fences, thinking blocks, and plain text.
    """
    text = text.strip()

    for pattern in (
        r"<\s*think\s*>.*?<\s*/\s*think\s*>",
        r"<think>.*?</think>",
    ):
        text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return sanitize_manim_code(match.group(1).strip())

    # Truncated responses often open a fence but never close it.
    match = re.search(r"```(?:python)?\s*\n(.*)", text, re.DOTALL)
    if match:
        return sanitize_manim_code(match.group(1).strip())

    if text.startswith("```"):
        text = re.sub(r"^```(?:python)?\s*\n?", "", text)

    return sanitize_manim_code(text.strip())


def extract_scene_class_names(code: str) -> list[str] | SceneParsingError:
    """Extract Scene class names from Manim code.

    Args:
        code: Python source code containing Manim scene definitions.

    Returns:
        A list of scene class names, or a SceneParsingError if parsing fails.
        Note: Returns the error as a value rather than raising to allow callers
        to handle parsing failures gracefully during the generation workflow.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return SceneParsingError(f"Syntax error in code: {e}")

    scene_names: list[str] = []
    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    # get scenes that inherit from 'Scene'
                    base_id = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                    if base_id.endswith("Scene"):
                        scene_names.append(node.name)
                        break
    except Exception as e:
        return SceneParsingError(f"Error extracting scene names: {e}")
    return scene_names
