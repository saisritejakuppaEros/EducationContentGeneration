import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
STAGES_DIR = SCRIPTS_DIR / "stages"
LEGACY_DIR = SCRIPTS_DIR / "legacy"
KNOWLEDGE_DIR = SCRIPTS_DIR / "knowledge"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
SAMPLES_DIR = SCRIPTS_DIR / "samples"
DIRECTOR_SKILL_PATH = KNOWLEDGE_DIR / "director_skill.md"
DEFAULT_GEMMA_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_LLM_BACKEND = "qwen"
DEFAULT_QWEN_MODEL = "Qwen/Qwen3.5-27B"
DEFAULT_QWEN_API_BASE = "http://localhost:8007/v1"
DEFAULT_QWEN_API_KEY = "sk-local"
DEFAULT_PERSON_DIR = PROJECT_ROOT / "assets" / "images"
DEFAULT_CARTOON_CAST_IMAGE = PROJECT_ROOT / "assets" / "cartoon" / "image.png"
TEXTBOOKS_OUTPUT_DIR = "textbooks"
STABLE_AUDIO_TFLITE_ROOT = PROJECT_ROOT / ".stable-audio-tflite"
DEFAULT_STABLE_AUDIO_HF_REPO = "stabilityai/stable-audio-3-optimized"

OUTPUT_ROOT_ENV = "PIPELINE_OUTPUT_ROOT"
_DEFAULT_OUTPUT_NAME = "output"
_OUTPUT_ROOT: Path | None = None


def _normalize_output_root(path: Path | str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    root = p.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_output_root() -> Path:
    global _OUTPUT_ROOT
    if _OUTPUT_ROOT is not None:
        return _OUTPUT_ROOT

    env = os.environ.get(OUTPUT_ROOT_ENV)
    if env:
        _OUTPUT_ROOT = _normalize_output_root(env)
    else:
        _OUTPUT_ROOT = _normalize_output_root(PROJECT_ROOT / _DEFAULT_OUTPUT_NAME)
    return _OUTPUT_ROOT


def set_output_root(path: Path | str | None) -> Path:
    global _OUTPUT_ROOT
    if path is None:
        _OUTPUT_ROOT = _normalize_output_root(PROJECT_ROOT / _DEFAULT_OUTPUT_NAME)
    else:
        _OUTPUT_ROOT = _normalize_output_root(path)
    os.environ[OUTPUT_ROOT_ENV] = str(_OUTPUT_ROOT)
    return _OUTPUT_ROOT


def bootstrap_output_root_from_argv(argv: list[str] | None = None) -> Path | None:
    """Apply --output-root from argv before module-level output defaults are built."""
    if os.environ.get(OUTPUT_ROOT_ENV):
        return get_output_root()

    argv = argv if argv is not None else sys.argv
    for index, arg in enumerate(argv):
        if arg == "--output-root" and index + 1 < len(argv):
            return set_output_root(argv[index + 1])
        if arg.startswith("--output-root="):
            return set_output_root(arg.split("=", 1)[1])
    return None


def add_output_root_argument(parser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Root folder for all pipeline outputs (default: output/). "
            "Example: output/run_a or output/compare_v2"
        ),
    )


def configure_output_root(path: Path | str | None = None) -> Path:
    if path is not None:
        return set_output_root(path)
    bootstrapped = bootstrap_output_root_from_argv()
    if bootstrapped is not None:
        return bootstrapped
    return get_output_root()


def output_dir(sub_module_name: str) -> Path:
    directory = get_output_root() / sub_module_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def project_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def resolve_project_path(rel_or_abs: str | Path) -> Path:
    path = Path(rel_or_abs)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


bootstrap_output_root_from_argv()
