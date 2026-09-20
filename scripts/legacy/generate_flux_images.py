#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import re
from pathlib import Path

import torch
from diffusers import Flux2Pipeline
from diffusers.utils import load_image
from PIL import Image

from paths import DEFAULT_PERSON_DIR, PROJECT_ROOT, output_dir

SUB_MODULE = "flux_images"
DEFAULT_PROMPTS = PROJECT_ROOT / "output" / "flux_prompts" / "flux_prompts.json"
DEFAULT_MODEL_HUB = Path("/workspace/parth/models/hub/models--black-forest-labs--FLUX.2-dev")

# Cast key -> filename inside assets/images/
DEFAULT_CAST_PHOTOS = {
    "F": "friend.png",
    "M": "ramanujan.jpeg",
}

NO_CHARACTER_HINTS = re.compile(
    r"no characters|no environment|math visualization|pure black|educational math",
    re.IGNORECASE,
)

_PIPELINE: Flux2Pipeline | None = None
_PIPELINE_MODEL_PATH: str | None = None


def resolve_model_snapshot(hub_dir: Path) -> Path:
    snapshots_dir = hub_dir / "snapshots"
    if snapshots_dir.is_dir():
        candidates = [p for p in snapshots_dir.iterdir() if p.is_dir()]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return hub_dir


def cast_photo_paths(person_dir: Path, cast_photos: dict[str, str]) -> dict[str, Path]:
    paths = {}
    for cast_key, filename in cast_photos.items():
        path = person_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing person photo for cast {cast_key}: {path}")
        paths[cast_key] = path
    return paths


def load_person_photo_cache(photo_paths: dict[str, Path]) -> dict[str, Image.Image]:
    cache: dict[str, Image.Image] = {}
    for cast_key, path in photo_paths.items():
        cache[cast_key] = load_image(str(path))
        print(f"Loaded person photo once: {path} ({cast_key})")
    return cache


def shot_text(shot: dict) -> str:
    structured = shot.get("flux_prompt_structured") or {}
    subject = structured.get("subject", "")
    return f"{shot.get('flux_prompt', '')} {subject} {shot.get('flux_frame', '')}"


def cast_match_patterns(cast_key: str, role: str) -> re.Pattern:
    role_pat = re.escape(role) if role else ""
    if cast_key == "M":
        return re.compile(
            rf"\bmathematician\b|\({cast_key.lower()}\)|\bm\b|\bm—|\bm'|\bm,|\bm and|\band m\b",
            re.IGNORECASE,
        )
    if cast_key == "F":
        return re.compile(
            rf"\bfriend\b|\({cast_key.lower()}\)|\bf—|\bf'|\bf,|\bf and|\band f\b",
            re.IGNORECASE,
        )
    parts = [rf"\({cast_key.lower()}\)", rf"\b{re.escape(cast_key)}\b"]
    if role_pat:
        parts.append(rf"\b{role_pat}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


def reference_cast_keys(shot: dict, cast: dict) -> list[str]:
    shot_type = (shot.get("type") or "").upper()
    if shot_type == "MATH INSERT":
        return []

    text = shot_text(shot)
    if NO_CHARACTER_HINTS.search(text):
        return []

    keys: list[str] = []
    for cast_key, info in cast.items():
        if cast_key not in DEFAULT_CAST_PHOTOS:
            continue
        role = (info.get("role") or "").strip()
        if cast_match_patterns(cast_key, role).search(text):
            keys.append(cast_key)
    return keys


def reference_images_for_shot(cast_keys: list[str], cache: dict[str, Image.Image]) -> list[Image.Image]:
    return [cache[key] for key in cast_keys]


def load_pipeline(model_path: Path, *, cpu_offload: bool, sequential_offload: bool) -> Flux2Pipeline:
    global _PIPELINE, _PIPELINE_MODEL_PATH

    model_key = str(model_path.resolve())
    if _PIPELINE is not None and _PIPELINE_MODEL_PATH == model_key:
        print("Reusing already-loaded FLUX 2.0 pipeline.")
        return _PIPELINE

    print(f"Loading FLUX 2.0 model once from {model_path} ...")
    pipe = Flux2Pipeline.from_pretrained(
        model_key,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    if hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()
    if hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if cpu_offload:
        if sequential_offload:
            pipe.enable_sequential_cpu_offload()
        else:
            pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    _PIPELINE = pipe
    _PIPELINE_MODEL_PATH = model_key
    print("Model loaded.")
    return pipe


def generate_shot_image(
    pipe: Flux2Pipeline,
    *,
    prompt: str,
    reference_images: list[Image.Image],
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
    width: int,
    height: int,
) -> Image.Image:
    generator = torch.Generator(device="cuda").manual_seed(seed)
    kwargs = {
        "prompt": prompt,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "width": width,
        "height": height,
        "generator": generator,
    }
    if reference_images:
        kwargs["image"] = reference_images if len(reference_images) > 1 else reference_images[0]

    result = pipe(**kwargs)
    return result.images[0]


def build_manifest_entry(
    *,
    scene_id: str,
    shot: dict,
    cast_keys: list[str],
    photo_paths: dict[str, Path],
    output_path: Path,
    seed: int,
) -> dict:
    return {
        "scene_id": scene_id,
        "shot": shot["shot"],
        "type": shot.get("type"),
        "output": str(output_path.relative_to(PROJECT_ROOT)),
        "person_photos_used": [str(photo_paths[k].relative_to(PROJECT_ROOT)) for k in cast_keys],
        "cast_reference_keys": cast_keys,
        "seed": seed,
        "flux_prompt": shot.get("flux_prompt"),
    }


def generate(
    *,
    prompts_path: Path,
    person_dir: Path,
    cast_photos: dict[str, str],
    model_path: Path,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
    width: int,
    height: int,
    cpu_offload: bool,
    sequential_offload: bool,
    skip_existing: bool,
) -> dict:
    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    cast = data.get("visual_style_guide", {}).get("cast", {})
    photo_paths = cast_photo_paths(person_dir, cast_photos)

    out_dir = output_dir(SUB_MODULE)
    manifest_path = out_dir / "manifest.json"
    manifest = {
        "story_title": data.get("story_title"),
        "prompts": str(prompts_path.relative_to(PROJECT_ROOT)),
        "person_dir": str(person_dir.relative_to(PROJECT_ROOT)),
        "cast_photos": {k: str(photo_paths[k].relative_to(PROJECT_ROOT)) for k in photo_paths},
        "model_path": str(model_path),
        "shots": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    scenes = data["scenes"]
    if scene_ids:
        scenes = [s for s in scenes if s["scene_id"] in scene_ids]
        if not scenes:
            raise ValueError(f"No scenes matched: {scene_ids}")

    pending: list[tuple[dict, dict, Path]] = []
    for scene in scenes:
        scene_dir = out_dir / scene["scene_id"]
        for shot in scene["shots"]:
            shot_num = shot["shot"]
            if shot_numbers and shot_num not in shot_numbers:
                continue
            output_path = scene_dir / f"{scene['scene_id']}_shot{shot_num:02d}.png"
            if skip_existing and output_path.is_file():
                print(f"Skipping existing {output_path.name}")
                continue
            pending.append((scene, shot, output_path))

    if not pending:
        print("Nothing to generate.")
        return manifest

    print(
        f"{len(pending)} shot(s) pending — "
        f"prompts: {prompts_path.name}, person photos from {person_dir}"
    )
    photo_cache = load_person_photo_cache(photo_paths)
    pipe = load_pipeline(model_path, cpu_offload=cpu_offload, sequential_offload=sequential_offload)

    for scene, shot, output_path in pending:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shot_num = shot["shot"]

        cast_keys = reference_cast_keys(shot, cast)
        reference_images = reference_images_for_shot(cast_keys, photo_cache)

        ref_label = "+".join(cast_keys) if cast_keys else "text-only"
        print(
            f"Generating {scene['scene_id']} shot {shot_num} "
            f"({ref_label}, {len(reference_images)} person photo(s))..."
        )

        shot_seed = seed + shot_num + (int(scene["scene_id"][1:]) * 100)
        image = generate_shot_image(
            pipe,
            prompt=shot["flux_prompt"],
            reference_images=reference_images,
            seed=shot_seed,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
        )
        image.save(output_path)

        entry = build_manifest_entry(
            scene_id=scene["scene_id"],
            shot=shot,
            cast_keys=cast_keys,
            photo_paths=photo_paths,
            output_path=output_path,
            seed=shot_seed,
        )
        manifest["shots"] = [
            e
            for e in manifest.get("shots", [])
            if not (e["scene_id"] == scene["scene_id"] and e["shot"] == shot_num)
        ]
        manifest["shots"].append(entry)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  Wrote {output_path}")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Flux 2.0 stills from person reference photos + flux_prompts.json."
        )
    )
    parser.add_argument(
        "--prompts",
        "--input",
        type=Path,
        default=DEFAULT_PROMPTS,
        dest="prompts",
        help=f"Shot prompts JSON (default: {DEFAULT_PROMPTS.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--person-dir",
        type=Path,
        default=DEFAULT_PERSON_DIR,
        help=f"Directory with cast reference photos (default: {DEFAULT_PERSON_DIR.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_HUB)
    parser.add_argument(
        "--scene",
        action="append",
        dest="scene_ids",
        help="Process only these scene ids (e.g. S0). Repeatable.",
    )
    parser.add_argument(
        "--shot",
        type=int,
        action="append",
        dest="shot_numbers",
        help="Process only these shot numbers within selected scenes. Repeatable.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=576)
    parser.add_argument(
        "--no-cpu-offload",
        action="store_true",
        help="Load full pipeline on GPU (needs lots of free VRAM).",
    )
    parser.add_argument(
        "--model-offload",
        action="store_true",
        help="Use model-level CPU offload (faster, needs more VRAM than default sequential offload).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip shots whose PNG already exists.",
    )
    args = parser.parse_args()

    if not args.prompts.is_file():
        raise FileNotFoundError(f"Prompts file not found: {args.prompts}")
    if not args.person_dir.is_dir():
        raise FileNotFoundError(f"Person photos directory not found: {args.person_dir}")

    model_path = resolve_model_snapshot(args.model_path)
    if not model_path.is_dir():
        raise FileNotFoundError(f"Model path not found: {model_path}")

    manifest = generate(
        prompts_path=args.prompts,
        person_dir=args.person_dir,
        cast_photos=DEFAULT_CAST_PHOTOS,
        model_path=model_path,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        seed=args.seed,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        width=args.width,
        height=args.height,
        cpu_offload=not args.no_cpu_offload,
        sequential_offload=not args.model_offload,
        skip_existing=args.skip_existing,
    )

    print(f"Done. {len(manifest.get('shots', []))} shots tracked in output/{SUB_MODULE}/manifest.json")


if __name__ == "__main__":
    main()
