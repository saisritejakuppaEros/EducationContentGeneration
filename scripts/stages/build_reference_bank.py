#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import shutil
from pathlib import Path

import torch
from diffusers import Flux2Pipeline
from diffusers.utils import load_image
from PIL import Image

from gemma_utils import fill_user_prompt, load_prompt_template
from cast_reference_utils import profile_reference_path, source_photo_path
from paths import (
    DEFAULT_GEMMA_MODEL,
    DEFAULT_LLM_BACKEND,
    DEFAULT_PERSON_DIR,
    PROJECT_ROOT,
    PROMPTS_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
    resolve_project_path,
)
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "series_profile"
DEFAULT_SERIES_PROFILE = output_dir(SUB_MODULE) / "series_profile.json"
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


def resolve_cast_source(
    *,
    cast_key: str,
    profile: dict,
    source_dir: Path,
    source_photos: dict[str, str],
) -> Path:
    path = profile_reference_path(profile, cast_key, "front_neutral")
    if path:
        return resolve_project_path(path).resolve()
    path = source_photo_path(cast_key, series_profile=profile, source_dir=source_dir)
    if path:
        return resolve_project_path(path).resolve()
    filename = source_photos.get(cast_key)
    if filename:
        legacy = source_dir / filename
        if legacy.is_file():
            return legacy
    raise FileNotFoundError(f"No source photo for cast {cast_key}")


def copy_source_as_front_neutral(
    *,
    cast_key: str,
    source_path: Path,
    out_root: Path,
) -> Path:
    dest = out_root / cast_key / "front_neutral.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file() or dest.stat().st_mtime < source_path.stat().st_mtime:
        shutil.copy2(source_path, dest)
        print(f"Copied source -> {project_rel(dest)}")
    return dest.resolve()


def mirror_tags_from_leader(*, leader_key: str, cast_key: str, out_root: Path, tags: list[str]) -> None:
    leader_dir = out_root / leader_key
    cast_dir = out_root / cast_key
    cast_dir.mkdir(parents=True, exist_ok=True)
    for tag in tags:
        src = leader_dir / f"{tag}.png"
        if not src.is_file():
            continue
        dest = cast_dir / f"{tag}.png"
        if not dest.is_file():
            shutil.copy2(src, dest)
            print(f"Mirrored {leader_key}/{tag} -> {cast_key}/{tag}")


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


def update_profile_reference_paths(profile: dict, out_root: Path) -> dict:
    for cast_key, info in profile.get("cast", {}).items():
        cast_dir = out_root / cast_key
        photos = []
        if cast_dir.is_dir():
            for png in sorted(cast_dir.glob("*.png")):
                tag = png.stem
                photos.append(
                    {
                        "tag": tag,
                        "path": project_rel(png),
                        "source": "generated" if tag != "front_neutral" else "master",
                    }
                )
        if photos:
            info["reference_photos"] = photos
    return profile


def build_bank(
    *,
    series_profile_path: Path,
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
    out_root = resolve_project_path(out_root).resolve()
    series_profile_path = resolve_project_path(series_profile_path).resolve()
    profile = json.loads(series_profile_path.read_text(encoding="utf-8"))
    visual_grammar = profile.get("visual_grammar", {})
    manifest = {"cast": {}, "generated": []}

    pipe = None
    if not copy_only:
        pipe = load_flux_pipeline(model_path, cpu_offload=cpu_offload)

    cast_keys = list(profile.get("cast", {}).keys())
    source_by_key: dict[str, Path] = {}
    for cast_key in cast_keys:
        try:
            source_by_key[cast_key] = resolve_cast_source(
                cast_key=cast_key,
                profile=profile,
                source_dir=source_dir,
                source_photos=source_photos,
            )
        except FileNotFoundError as exc:
            print(f"Skipping {cast_key} — {exc}")

    leader_key = "Y" if "Y" in source_by_key else next(iter(source_by_key), None)
    if not leader_key:
        raise FileNotFoundError("No cast sources found in series profile or --source")

    front_by_key: dict[str, Path] = {}
    for cast_key, source_path in source_by_key.items():
        cast_dir = out_root / cast_key
        cast_dir.mkdir(parents=True, exist_ok=True)
        front_path = copy_source_as_front_neutral(
            cast_key=cast_key,
            source_path=source_path,
            out_root=out_root,
        )
        front_by_key[cast_key] = front_path
        manifest["cast"][cast_key] = {"front_neutral": project_rel(front_path)}

    def generate_tags_for(cast_key: str) -> None:
        cast_dir = out_root / cast_key
        front_path = front_by_key[cast_key]
        if copy_only:
            for tag in tags:
                if tag == "front_neutral":
                    continue
                dest = cast_dir / f"{tag}.png"
                if not dest.is_file() and not skip_existing:
                    shutil.copy2(front_path, dest)
            return
        if pipe is None:
            return

        info = profile.get("cast", {}).get(cast_key, {})
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
            manifest["generated"].append(project_rel(dest))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    generate_tags_for(leader_key)

    leader_source = source_by_key[leader_key].resolve()
    for cast_key in source_by_key:
        if cast_key == leader_key:
            continue
        if source_by_key[cast_key].resolve() == leader_source:
            mirror_tags_from_leader(leader_key=leader_key, cast_key=cast_key, out_root=out_root, tags=tags)
        else:
            generate_tags_for(cast_key)

    updated = update_profile_reference_paths(profile, out_root)
    write_json(series_profile_path, updated)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-angle reference photo bank for M/F/Y.")
    parser.add_argument("--series-profile", type=Path, default=DEFAULT_SERIES_PROFILE)
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
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    if not args.series_profile.is_file():
        raise FileNotFoundError(f"series_profile not found: {args.series_profile}")

    tags = args.tags or list(TAG_EDIT_HINTS.keys())
    model_path = resolve_model_snapshot(args.model_path)

    manifest = build_bank(
        series_profile_path=args.series_profile,
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
