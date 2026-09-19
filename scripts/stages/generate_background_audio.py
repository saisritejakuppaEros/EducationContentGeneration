#!/usr/bin/env python3
"""Generate background music / ambience via Stable Audio 3 (TFLite / CPU).

Weights are pulled from Hugging Face: stabilityai/stable-audio-3-optimized
(on first run or via scripts/setup_stable_audio.sh).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from paths import (
    DEFAULT_STABLE_AUDIO_HF_REPO,
    PROJECT_ROOT,
    STABLE_AUDIO_TFLITE_ROOT,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
)

SUB_MODULE = "background_audio"


def default_storyboard_path() -> Path:
    return output_dir("storyboard") / "storyboard.json"


def default_directing_package_path() -> Path:
    return output_dir("directing") / "directing_package.json"

DEFAULT_EDU_BGM_PROMPT = (
    "Soft cinematic background music for an educational science video, "
    "gentle piano and warm synth pads, thoughtful and curious mood, "
    "no vocals, no drums, 90 BPM"
)

DIT_FOR_USE = {
    "music": ("sm-music", "same-s"),
    "sfx": ("sm-sfx", "same-s"),
    "score": ("sm-music", "same-s"),
}


def ensure_hf_env() -> None:
    hub = os.environ.get("HF_HOME") or "/workspace/teja/models/hub"
    os.environ.setdefault("HF_HOME", hub)
    os.environ.setdefault("HF_HUB_CACHE", hub)


def tflite_python() -> Path:
    py = STABLE_AUDIO_TFLITE_ROOT / ".venv" / "bin" / "python"
    if not py.is_file():
        raise FileNotFoundError(
            "Stable Audio TFLite venv not found. Run:\n"
            "  bash scripts/setup_stable_audio.sh"
        )
    return py


def sa3_script() -> Path:
    script = STABLE_AUDIO_TFLITE_ROOT / "scripts" / "sa3_tflite.py"
    if not script.is_file():
        raise FileNotFoundError(
            f"Missing {script}. Run:\n"
            "  bash scripts/setup_stable_audio.sh"
        )
    return script


def run_sa3_generation(
    *,
    prompt: str,
    out_path: Path,
    seconds: float,
    dit: str,
    decoder: str,
    seed: int | None,
    negative_prompt: str | None,
    cfg: float,
) -> None:
    ensure_hf_env()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(tflite_python()),
        str(sa3_script()),
        "--prompt",
        prompt,
        "--dit",
        dit,
        "--decoder",
        decoder,
        "--seconds",
        str(seconds),
        "--out",
        str(out_path),
        "--cfg",
        str(cfg),
    ]
    if negative_prompt:
        cmd.extend(["--negative-prompt", negative_prompt])
    if seed is not None:
        cmd.extend(["--seed", str(seed)])

    print(f"Stable Audio HF repo: {DEFAULT_STABLE_AUDIO_HF_REPO}")
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=STABLE_AUDIO_TFLITE_ROOT)


def scene_bgm_prompt(scene: dict) -> str:
    mood = scene.get("mood") or scene.get("tone") or "curious, educational"
    setting = scene.get("setting") or scene.get("location") or "abstract learning space"
    return (
        f"Instrumental background bed for an educational video scene. "
        f"Setting: {setting}. Mood: {mood}. "
        "Gentle, unobtrusive, no vocals, suitable under narration."
    )


def _parse_timestamp(ts: str) -> float:
    ts = (ts or "0:00").strip()
    if ":" not in ts:
        return float(ts)
    parts = ts.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def generate_from_directing_package(
    package_path: Path,
    *,
    dit: str,
    decoder: str,
    seed: int | None,
) -> dict:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    cues = package.get("audio_cue_sheet") or []
    if not cues:
        raise ValueError("directing_package.json has no audio_cue_sheet (director Sec. 7.2)")

    out_dir = output_dir(SUB_MODULE) / "cues"
    entries: list[dict] = []

    for cue in cues:
        cue_id = cue.get("cue_id") or f"M{len(entries) + 1}"
        start = _parse_timestamp(cue.get("time_start", "0:00"))
        end = _parse_timestamp(cue.get("time_end", "0:30"))
        duration = max(5.0, end - start)
        prompt = cue.get("stable_audio_prompt") or (
            f"Instrumental background bed. Mood: {cue.get('mood', 'curious')}. "
            f"Instruments: {cue.get('instruments', 'soft strings and pad')}. "
            "Educational explainer, no vocals, mix under narration."
        )
        wav_path = out_dir / f"{cue_id}.wav"
        run_sa3_generation(
            prompt=prompt,
            out_path=wav_path,
            seconds=duration,
            dit=dit,
            decoder=decoder,
            seed=seed,
            negative_prompt="vocals, lyrics, harsh percussion, distracting SFX",
            cfg=2.0,
        )
        entries.append(
            {
                "cue_id": cue_id,
                "time_start": cue.get("time_start"),
                "time_end": cue.get("time_end"),
                "duration_seconds": duration,
                "prompt": prompt,
                "path": str(wav_path.relative_to(get_output_root())).replace("\\", "/"),
            }
        )

    manifest = {
        "model_repo": DEFAULT_STABLE_AUDIO_HF_REPO,
        "backend": "tflite-cpu",
        "source": str(package_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "cues": entries,
    }
    manifest_path = output_dir(SUB_MODULE) / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def generate_from_storyboard(
    storyboard_path: Path,
    *,
    seconds: float,
    dit: str,
    decoder: str,
    seed: int | None,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    out_dir = output_dir(SUB_MODULE) / "scenes"
    entries: list[dict] = []

    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        duration = float(scene.get("duration_seconds") or seconds)
        prompt = scene_bgm_prompt(scene)
        wav_path = out_dir / f"{scene_id}_bgm.wav"
        run_sa3_generation(
            prompt=prompt,
            out_path=wav_path,
            seconds=duration,
            dit=dit,
            decoder=decoder,
            seed=seed,
            negative_prompt="vocals, loud drums, distracting SFX",
            cfg=2.0,
        )
        entries.append(
            {
                "scene_id": scene_id,
                "prompt": prompt,
                "duration_seconds": duration,
                "path": str(wav_path.relative_to(get_output_root())).replace("\\", "/"),
            }
        )

    manifest = {
        "model_repo": DEFAULT_STABLE_AUDIO_HF_REPO,
        "backend": "tflite-cpu",
        "scenes": entries,
    }
    manifest_path = output_dir(SUB_MODULE) / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def generate_sample(
    *,
    prompt: str,
    seconds: float,
    dit: str,
    decoder: str,
    seed: int | None,
    out_name: str,
) -> Path:
    out_path = output_dir(SUB_MODULE) / "samples" / out_name
    run_sa3_generation(
        prompt=prompt,
        out_path=out_path,
        seconds=seconds,
        dit=dit,
        decoder=decoder,
        seed=seed,
        negative_prompt="vocals, harsh percussion",
        cfg=2.0,
    )
    meta = {
        "model_repo": DEFAULT_STABLE_AUDIO_HF_REPO,
        "backend": "tflite-cpu",
        "prompt": prompt,
        "seconds": seconds,
        "dit": dit,
        "decoder": decoder,
        "path": str(out_path.relative_to(get_output_root())).replace("\\", "/"),
    }
    meta_path = out_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate background music/SFX with Stable Audio 3 (CPU TFLite)."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Generate a single demo WAV under output/background_audio/samples/.",
    )
    parser.add_argument("--prompt", default=DEFAULT_EDU_BGM_PROMPT)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument(
        "--kind",
        choices=list(DIT_FOR_USE),
        default="music",
        help="Preset: music/score → sm-music, sfx → sm-sfx.",
    )
    parser.add_argument("--dit", choices=["sm-music", "sm-sfx", "medium"], default=None)
    parser.add_argument("--decoder", choices=["same-s", "same-l"], default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--storyboard", type=Path, default=None)
    parser.add_argument(
        "--directing-package",
        type=Path,
        nargs="?",
        const=True,
        default=None,
        help="Generate BGM from output/directing/directing_package.json audio_cue_sheet.",
    )
    parser.add_argument(
        "--out-name",
        default="edu_bgm_sample.wav",
        help="Filename for --sample output.",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    dit = args.dit or DIT_FOR_USE[args.kind][0]
    decoder = args.decoder or DIT_FOR_USE[args.kind][1]
    if dit == "medium" and decoder == "same-s":
        decoder = "same-l"

    if args.directing_package is not None:
        path = (
            args.directing_package
            if isinstance(args.directing_package, Path) and args.directing_package.is_file()
            else default_directing_package_path()
        )
        if not path.is_file():
            raise FileNotFoundError(f"directing package not found: {path}")
        manifest = generate_from_directing_package(
            path,
            dit=dit,
            decoder=decoder,
            seed=args.seed,
        )
        print(f"Wrote {output_dir(SUB_MODULE) / 'manifest.json'} ({len(manifest['cues'])} cues)")
        return

    if args.storyboard:
        path = args.storyboard if args.storyboard.is_file() else default_storyboard_path()
        if not path.is_file():
            raise FileNotFoundError(f"storyboard not found: {path}")
        manifest = generate_from_storyboard(
            path,
            seconds=args.seconds,
            dit=dit,
            decoder=decoder,
            seed=args.seed,
        )
        print(f"Wrote {output_dir(SUB_MODULE) / 'manifest.json'} ({len(manifest['scenes'])} scenes)")
        return

    if not args.sample and args.prompt == DEFAULT_EDU_BGM_PROMPT:
        parser.error("Pass --sample, --storyboard, --directing-package, or a custom --prompt.")

    out_path = generate_sample(
        prompt=args.prompt,
        seconds=args.seconds,
        dit=dit,
        decoder=decoder,
        seed=args.seed,
        out_name=args.out_name,
    )
    print(f"Wrote {project_rel(out_path)}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
