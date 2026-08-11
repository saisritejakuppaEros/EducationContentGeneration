#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

import torch
from diffusers import Flux2Pipeline
from diffusers.utils import load_image
from PIL import Image

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_GEMMA_MODEL, DEFAULT_LLM_BACKEND, DEFAULT_PERSON_DIR, PROJECT_ROOT, PROMPTS_DIR, output_dir
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "series_bible"
DEFAULT_SERIES_BIBLE = output_dir(SUB_MODULE) / "series_bible.json"
DEFAULT_PROMPT = PROMPTS_DIR / "reference_bank.md"
DEFAULT_MODEL_HUB = Path("/workspace/parth/models/hub/models--black-forest-labs--FLUX.2-dev")

DEFAULT_SOURCE_PHOTOS = {
    "M": "ramanujan.jpeg",
    "F": "friend.png",
    "Y": "friend.png",
}

TAG_EDIT_HINTS = {
    "front_neutral": "front-facing neutral expression, eye level",
    "three_quarter_left": "three-quarter view facing left, neutral expression",
    "three_quarter_right": "three-quarter view facing right, neutral expression",
    "profile": "side profile view, neutral expression",
    "close_up_neutral": "close-up face, neutral expression, 85mm lens",
    "close_up_expression_concerned": "close-up face, concerned expression",
    "close_up_expression_curious": "close-up face, curious expression",
    "wide_full_body_neutral_pose": "full body wide shot, neutral standing pose, 24mm lens",
}

_PIPELINE: Flux2Pipeline | None = None


def resolve_model_snapshot(hub_dir: Path) -> Path:
    snapshots_dir = hub_dir / "snapshots"
    if snapshots_dir.is_dir():
        candidates = [p for p in snapshots_dir.iterdir() if p.is_dir()]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return hub_dir


def load_flux_pipeline(model_path: Path, *, cpu_offload: bool) -> Flux2Pipeline:
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    print(f"Loading FLUX.2-dev from {model_path} ...")
    pipe = Flux2Pipeline.from_pretrained(
        str(model_path.resolve()),
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    if cpu_offload:
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.to("cuda")
    _PIPELINE = pipe
    return pipe


def copy_source_as_front_neutral(
    *,
    cast_key: str,
    source_dir: Path,
    source_photos: dict[str, str],
    out_root: Path,
) -> Path:
    filename = source_photos.get(cast_key)
    if not filename:
        raise ValueError(f"No source photo configured for cast {cast_key}")
    src = source_dir / filename
    if not src.is_file():
        raise FileNotFoundError(f"Source photo not found: {src}")

    dest = out_root / cast_key / "front_neutral.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        shutil.copy2(src, dest)
        print(f"Copied source -> {dest.relative_to(PROJECT_ROOT)}")
    return dest


def generate_bank_image(
    pipe: Flux2Pipeline,
    *,
    source_image: Image.Image,
    edit_prompt: str,
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
) -> Image.Image:
    generator = torch.Generator(device="cuda").manual_seed(seed)
    result = pipe(
        image=[source_image],
        prompt=edit_prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=generator,
    )
    return result.images[0]


def build_edit_prompt(
    *,
    cast_key: str,
    tag: str,
    character_description: str,
    visual_grammar: dict,
    backend: str,
    model_path: Path,
    prompt_path: Path,
) -> str:
    hint = TAG_EDIT_HINTS.get(tag, tag.replace("_", " "))
    if tag == "front_neutral":
        return (
            f"The person from image one, {hint}, {character_description}, "
            f"{visual_grammar.get('grade', '')}, identity preserved exactly"
        )

    system_prompt, user_template = load_prompt_template(prompt_path)

    def validate(data: dict) -> None:
        if "edit_prompt" not in data:
            raise ValueError("Missing edit_prompt")

    data = run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            character_key=cast_key,
            tag=tag,
            character_description=character_description,
            visual_grammar=json.dumps(visual_grammar, indent=2),
        ),
        validate=validate,
        model_path=model_path,
        max_new_tokens=1024,
        max_tokens=1024,
    )
    return data["edit_prompt"]


def update_bible_paths(bible: dict, out_root: Path) -> dict:
    for cast_key, info in bible.get("cast", {}).items():
        photos = []
        for entry in info.get("reference_photos") or []:
            tag = entry.get("tag", "front_neutral")
            rel = out_root.relative_to(PROJECT_ROOT) / cast_key / f"{tag}.png"
            photos.append(
                {
                    "tag": tag,
                    "path": str(rel).replace("\\", "/"),
                    "source": entry.get("source", "generated"),
                }
            )
        info["reference_photos"] = photos
    return bible


def build_bank(
    *,
    series_bible_path: Path,
    source_dir: Path,
    source_photos: dict[str, str],
    out_root: Path,
    model_path: Path,
    prompt_path: Path,
    backend: str,
    gemma_model_path: Path,
    tags: list[str],
    skip_existing: bool,
    copy_only: bool,
    cpu_offload: bool,
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
) -> dict:
    bible = json.loads(series_bible_path.read_text(encoding="utf-8"))
    visual_grammar = bible.get("visual_grammar", {})
    manifest = {"cast": {}, "generated": []}

    pipe = None
    if not copy_only:
        pipe = load_flux_pipeline(model_path, cpu_offload=cpu_offload)

    for cast_key, info in bible.get("cast", {}).items():
        if cast_key not in source_photos:
            print(f"Skipping {cast_key} — no source photo mapping")
            continue

        cast_dir = out_root / cast_key
        cast_dir.mkdir(parents=True, exist_ok=True)
        front_path = copy_source_as_front_neutral(
            cast_key=cast_key,
            source_dir=source_dir,
            source_photos=source_photos,
            out_root=out_root,
        )
        manifest["cast"][cast_key] = {"front_neutral": str(front_path.relative_to(PROJECT_ROOT))}

        if copy_only:
            for tag in tags:
                if tag == "front_neutral":
                    continue
                dest = cast_dir / f"{tag}.png"
                if not dest.is_file() and not skip_existing:
                    shutil.copy2(front_path, dest)
            continue

        source_image = load_image(str(front_path)).convert("RGB")
        description = info.get("description", cast_key)

        for tag in tags:
            if tag == "front_neutral":
                continue
            dest = cast_dir / f"{tag}.png"
            if skip_existing and dest.is_file():
                print(f"Skipping existing {dest.name}")
                continue

            edit_prompt = build_edit_prompt(
                cast_key=cast_key,
                tag=tag,
                character_description=description,
                visual_grammar=visual_grammar,
                backend=backend,
                model_path=gemma_model_path,
                prompt_path=prompt_path,
            )
            print(f"Generating {cast_key}/{tag} ...")
            shot_seed = seed + hash(f"{cast_key}:{tag}") % 10000
            image = generate_bank_image(
                pipe,
                source_image=source_image,
                edit_prompt=edit_prompt,
                seed=shot_seed,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
            )
            image.save(dest)
            manifest["generated"].append(str(dest.relative_to(PROJECT_ROOT)))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    updated = update_bible_paths(bible, out_root)
    write_json(series_bible_path, updated)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-angle reference photo bank for M/F/Y.")
    parser.add_argument("--series-bible", type=Path, default=DEFAULT_SERIES_BIBLE)
    parser.add_argument("--source", type=Path, default=DEFAULT_PERSON_DIR)
    parser.add_argument("--output-dir", type=Path, default=output_dir(SUB_MODULE) / "reference_photos")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_HUB)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--gemma-model-path", type=Path, default=DEFAULT_GEMMA_MODEL)
    parser.add_argument("--tag", action="append", dest="tags", help="Tags to generate (repeatable).")
    parser.add_argument("--copy-only", action="store_true", help="Copy front_neutral to all tags (no Flux).")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-cpu-offload", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    args = parser.parse_args()

    if not args.series_bible.is_file():
        raise FileNotFoundError(f"series_bible not found: {args.series_bible}")

    tags = args.tags or list(TAG_EDIT_HINTS.keys())
    model_path = resolve_model_snapshot(args.model_path)

    manifest = build_bank(
        series_bible_path=args.series_bible,
        source_dir=args.source,
        source_photos=DEFAULT_SOURCE_PHOTOS,
        out_root=args.output_dir,
        model_path=model_path,
        prompt_path=args.prompt,
        backend=args.backend,
        gemma_model_path=args.gemma_model_path,
        tags=tags,
        skip_existing=args.skip_existing,
        copy_only=args.copy_only,
        cpu_offload=not args.no_cpu_offload,
        seed=args.seed,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
    )

    manifest_path = args.output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    write_gate("reference_bank", passed=True, notes="Review reference photos manually")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
