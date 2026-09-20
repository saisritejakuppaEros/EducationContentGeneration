#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path

import torch
from diffusers import Flux2Pipeline
from diffusers.utils import load_image
from PIL import Image, ImageDraw

from cast_reference_utils import infer_characters_in_frame, resolve_cast_reference
from paths import DEFAULT_PERSON_DIR, PROJECT_ROOT, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel
from pixels_storyboard import apply_keyframes_to_decomposition

SUB_MODULE = "storyboard"
DEFAULT_STORYBOARD = output_dir(SUB_MODULE) / "storyboard.json"
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"
DEFAULT_MODEL_HUB = Path("/workspace/parth/models/hub/models--black-forest-labs--FLUX.2-dev")

_PIPELINE: Flux2Pipeline | None = None


def resolve_model_snapshot(hub_dir: Path) -> Path:
    snapshots_dir = hub_dir / "snapshots"
    if snapshots_dir.is_dir():
        candidates = [p for p in snapshots_dir.iterdir() if p.is_dir()]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return hub_dir


def load_pipeline(model_path: Path, *, cpu_offload: bool) -> Flux2Pipeline:
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


def bank_lookup(series_bible: dict, cast_key: str, tag: str) -> Path | None:
    cast = series_bible.get("cast", {}).get(cast_key, {})
    for entry in cast.get("reference_photos") or []:
        if entry.get("tag") == tag:
            path = PROJECT_ROOT / entry["path"]
            if path.is_file():
                return path
    for entry in cast.get("reference_photos") or []:
        if entry.get("tag") == "front_neutral":
            path = PROJECT_ROOT / entry["path"]
            if path.is_file():
                return path
    return None


def set_reference_image(series_bible: dict, location_hint: str) -> Path | None:
    sets = series_bible.get("world", {}).get("sets") or []
    if not sets:
        return None
    location_lower = (location_hint or "").lower()
    for entry in sets:
        name = (entry.get("name") or "").lower()
        if name and name in location_lower:
            ref = entry.get("reference_image")
            if ref:
                path = PROJECT_ROOT / ref
                if path.is_file():
                    return path
    ref = sets[0].get("reference_image")
    if ref:
        path = PROJECT_ROOT / ref
        if path.is_file():
            return path
    return None


def build_face_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = size
    draw.ellipse((w * 0.25, h * 0.1, w * 0.75, h * 0.65), fill=255)
    return mask


def generate_keyframe(
    pipe: Flux2Pipeline,
    *,
    images: list[Image.Image],
    prompt: str,
    mask: Image.Image | None,
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
    if images:
        kwargs["image"] = images if len(images) > 1 else images[0]
    if mask is not None:
        kwargs["mask_image"] = mask
    result = pipe(**kwargs)
    return result.images[0]


def generate(
    *,
    storyboard_path: Path,
    series_bible_path: Path,
    model_path: Path,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
    width: int,
    height: int,
    cpu_offload: bool,
    skip_existing: bool,
    mask_retry: bool,
    include_math_inserts: bool = False,
    keyframes_subdir: str = "storyboard",
    decomposition_path: Path | None = None,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    series_bible = json.loads(series_bible_path.read_text(encoding="utf-8"))
    out_dir = get_output_root() / keyframes_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "keyframes_manifest.json"
    manifest = {"shots": []}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pending: list[tuple[dict, dict, Path]] = []
    for scene in storyboard.get("scenes", []):
        if scene_ids and scene["scene_id"] not in scene_ids:
            continue
        for shot in scene.get("shots", []):
            if shot_numbers and shot["shot"] not in shot_numbers:
                continue
            if not include_math_inserts and (shot.get("type") or "").upper() == "MATH INSERT":
                continue
            output_path = PROJECT_ROOT / shot.get("keyframe_image", "")
            if not str(output_path).endswith(".png"):
                output_path = out_dir / scene["scene_id"] / f"{scene['scene_id']}_shot{shot['shot']:02d}.png"
            if skip_existing and output_path.is_file():
                print(f"Skipping existing {output_path.name}")
                continue
            pending.append((scene, shot, output_path))

    if not pending:
        print("Nothing to generate.")
        return manifest

    print(f"{len(pending)} keyframe(s) pending")
    pipe = load_pipeline(model_path, cpu_offload=cpu_offload)

    for scene, shot, output_path in pending:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]

        images: list[Image.Image] = []
        image_index = 1
        prompt_parts: list[str] = []
        reference_log: list[dict] = []

        base_path = set_reference_image(series_bible, scene.get("title", ""))
        if base_path:
            images.append(load_image(str(base_path)).convert("RGB"))
            prompt_parts.append(f"environment from image {image_index}")
            reference_log.append({"type": "environment", "path": str(base_path.relative_to(PROJECT_ROOT))})
            image_index += 1

        ref_tags = shot.get("reference_tags_used") or {}
        cast = series_bible.get("cast", {})
        characters = infer_characters_in_frame(shot, cast)
        for cast_key in characters:
            tag = ref_tags.get(cast_key, "front_neutral")
            ref_path, ref_source = resolve_cast_reference(
                series_bible=series_bible,
                cast_key=cast_key,
                tag=tag,
                bank_lookup=bank_lookup,
                source_dir=DEFAULT_PERSON_DIR,
            )
            if ref_path:
                images.append(load_image(str(ref_path)).convert("RGB"))
                prompt_parts.append(f"the character {cast_key} from image {image_index}, identity preserved exactly")
                reference_log.append(
                    {
                        "cast": cast_key,
                        "tag": tag,
                        "source": ref_source,
                        "path": str(ref_path.relative_to(PROJECT_ROOT)),
                    }
                )
                image_index += 1
            else:
                print(f"Warning: no reference photo for {scene_id} shot {shot_num} character {cast_key}")

        flux_prompt = shot.get("flux_prompt") or shot.get("flux_frame") or shot.get("image_caption") or ""
        indexed_refs = ", ".join(prompt_parts)
        full_prompt = f"{flux_prompt}. {indexed_refs}." if indexed_refs else flux_prompt

        shot_seed = seed + shot_num + (hash(scene_id) % 1000)
        image = generate_keyframe(
            pipe,
            images=images,
            prompt=full_prompt,
            mask=None,
            seed=shot_seed,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
        )

        if mask_retry and shot.get("characters_in_frame"):
            cast_key = shot["characters_in_frame"][0]
            tag = ref_tags.get(cast_key, "close_up_neutral")
            ref_path = bank_lookup(series_bible, cast_key, tag)
            if ref_path:
                mask = build_face_mask(image.size)
                ref_img = load_image(str(ref_path)).convert("RGB")
                image = generate_keyframe(
                    pipe,
                    images=[image, ref_img],
                    prompt=f"the face of character {cast_key} from image two, identity preserved exactly",
                    mask=mask,
                    seed=shot_seed + 1,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    width=width,
                    height=height,
                )

        image.save(output_path)
        shot["qc_status"] = "generated"
        entry = {
            "scene_id": scene_id,
            "shot": shot_num,
            "output": str(output_path.relative_to(PROJECT_ROOT)),
            "seed": shot_seed,
            "references_used": len(images),
            "characters_in_frame": characters,
            "reference_details": reference_log,
        }
        manifest["shots"] = [
            e for e in manifest.get("shots", []) if not (e["scene_id"] == scene_id and e["shot"] == shot_num)
        ]
        manifest["shots"].append(entry)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  Wrote {output_path}")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    storyboard_path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if decomposition_path and decomposition_path.is_file():
        apply_keyframes_to_decomposition(decomposition_path, manifest.get("shots") or [])
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate storyboard keyframe PNGs with FLUX.2-dev.")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--series-bible", type=Path, default=DEFAULT_SERIES_BIBLE)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_HUB)
    parser.add_argument("--scene", action="append", dest="scene_ids")
    parser.add_argument("--shot", type=int, action="append", dest="shot_numbers")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=576)
    parser.add_argument("--no-cpu-offload", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--include-math-inserts",
        action="store_true",
        help="Generate keyframes for MATH INSERT shots (use when Manim is disabled).",
    )
    parser.add_argument("--mask-retry", action="store_true", help="Run face mask inpaint pass after base keyframe.")
    parser.add_argument(
        "--keyframes-subdir",
        type=str,
        default="storyboard",
        help="Subfolder under --output-root for PNG keyframes (e.g. shots/keyframes).",
    )
    parser.add_argument(
        "--shot-decomposition",
        type=Path,
        default=None,
        help="If set, sync keyframe paths back into this shot_decomposition.json.",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    if not args.storyboard.is_file():
        raise FileNotFoundError(f"storyboard not found: {args.storyboard}")
    if not args.series_bible.is_file():
        raise FileNotFoundError(f"series_bible not found: {args.series_bible}")

    model_path = resolve_model_snapshot(args.model_path)
    manifest = generate(
        storyboard_path=args.storyboard,
        series_bible_path=args.series_bible,
        model_path=model_path,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        seed=args.seed,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        width=args.width,
        height=args.height,
        cpu_offload=not args.no_cpu_offload,
        skip_existing=args.skip_existing,
        mask_retry=args.mask_retry,
        include_math_inserts=args.include_math_inserts,
        keyframes_subdir=args.keyframes_subdir,
        decomposition_path=args.shot_decomposition,
    )
    print(f"Done. {len(manifest.get('shots', []))} keyframes in {project_rel(get_output_root() / args.keyframes_subdir)}/")


if __name__ == "__main__":
    main()
