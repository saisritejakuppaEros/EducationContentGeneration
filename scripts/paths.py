from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def output_dir(sub_module_name: str) -> Path:
    directory = PROJECT_ROOT / "output" / sub_module_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory
