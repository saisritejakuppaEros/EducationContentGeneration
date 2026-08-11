from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
SAMPLES_DIR = SCRIPTS_DIR / "samples"
DEFAULT_GEMMA_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_LLM_BACKEND = "qwen"
DEFAULT_QWEN_MODEL = "Qwen/Qwen3.5-27B"
DEFAULT_QWEN_API_BASE = "http://localhost:8000/v1"
DEFAULT_QWEN_API_KEY = "sk-local"
DEFAULT_PERSON_DIR = PROJECT_ROOT / "assets" / "images"


def output_dir(sub_module_name: str) -> Path:
    directory = PROJECT_ROOT / "output" / sub_module_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory
