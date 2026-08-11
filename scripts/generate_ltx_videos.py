#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import torch
from diffusers.utils import load_image
from PIL import Image

from paths import PROJECT_ROOT, output_dir

SUB_MODULE = "ltx_videos"
DEFAULT_PROMPTS = PROJECT_ROOT / "output" / "ltx_prompts" / "ltx_prompts.json"
DEFAULT_MODEL = "diffusers/LTX-2.3-Diffusers"
DEFAULT_TALKING_HEAD_LORA = "elix3r/LTX-2.3-22b-AV-LoRA-talking-head"
DEFAULT_TALKING_HEAD_WEIGHT = "LTX-2.3-22b-AV-LoRA-talking-head-v1.safetensors"
DEFAULT_HF_HOME = Path("/workspace/teja/models/hub")

DEFAULT_NEGATIVE = (
    "music, silent or muted audio, distorted voice, off-sync lips, background music, "
    "washed out contrast, deformed facial features, out of focus face, unnatural skin tones, "
    "blurry, jittery, low quality, worst quality"
)

_PIPE = None
_PIPE_KEY: str | None = None
_TALKING_HEAD_LOADED = False


def require_ltx2_diffusers():
    try:
        from diffusers import LTX2ImageToVideoPipeline
        from diffusers.utils import encode_video
    except ImportError as exc:
        raise SystemExit(
            "LTX 2.3 audio-video requires diffusers>=0.39 with LTX2 support.\n"
            "Install in gsplat_env:\n"
            "  pip install 'diffusers>=0.39.0'\n"
            f"Original error: {exc}"
        ) from exc
    return LTX2ImageToVideoPipeline, encode_video


def configure_model_cache(hf_home: Path) -> None:
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HF_HUB_CACHE"] = str(hf_home)
    os.environ.pop("TORCH_HOME", None)


def snap_dim(value: int, step: int = 32) -> int:
    return max(step, (value // step) * step)


def frames_for_duration(
    duration_seconds: float,
    *,
    preferred_fps: float,
    max_frames: int,
) -> tuple[int, float]:
    target = int(round(duration_seconds * preferred_fps))
    target = max(9, min(max_frames, target))
    k = max(1, round((target - 1) / 8))
    num_frames = 8 * k + 1
    frame_rate = num_frames / duration_seconds
    return num_frames, frame_rate


def resolve_init_image(path: Path, width: int, height: int) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Init image not found: {path}")
    image = load_image(str(path)).convert("RGB")
    return image.resize((width, height), Image.Resampling.LANCZOS)


def load_pipeline(
    *,
    model_id: str,
    local_files_only: bool,
    cpu_offload: bool,
    sequential_offload: bool,
):
    global _PIPE, _PIPE_KEY

    LTX2ImageToVideoPipeline, _ = require_ltx2_diffusers()
    model_key = f"{model_id}|local={local_files_only}|cpu={cpu_offload}|seq={sequential_offload}"
    if _PIPE is not None and _PIPE_KEY == model_key:
        print("Reusing already-loaded LTX 2.3 pipeline.")
        return _PIPE

    print(f"Loading LTX 2.3 I2V pipeline from {model_id} ...")
    pipe = LTX2ImageToVideoPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        local_files_only=local_files_only,
    )
    if hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if cpu_offload:
        if sequential_offload:
            pipe.enable_sequential_cpu_offload(device="cuda")
        else:
            pipe.enable_model_cpu_offload(device="cuda")
    else:
        pipe.to("cuda")

    _PIPE = pipe
    _PIPE_KEY = model_key
    print("LTX pipeline loaded.")
    return pipe


def configure_talking_head_lora(
    pipe,
    *,
    lora_repo: str,
    weight_name: str,
    lora_weight: float,
    enabled: bool,
) -> None:
    global _TALKING_HEAD_LOADED

    if enabled:
        if not _TALKING_HEAD_LOADED:
            print(f"Loading talking-head LoRA: {lora_repo}/{weight_name}")
            pipe.load_lora_weights(
                lora_repo,
                adapter_name="talking_head",
                weight_name=weight_name,
            )
            _TALKING_HEAD_LOADED = True
        pipe.set_adapters(["talking_head"], adapter_weights=[lora_weight])
    elif _TALKING_HEAD_LOADED:
        if hasattr(pipe, "disable_lora"):
            pipe.disable_lora()
        elif hasattr(pipe, "disable_adapters"):
            pipe.disable_adapters()
        else:
            pipe.set_adapters([], adapter_weights=[])


def generate_shot_video(
    pipe,
    *,
    image: Image.Image,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: float,
    seed: int,
    num_inference_steps: int,
    guidance_scale: float,
    audio_guidance_scale: float,
    stg_scale: float,
    modality_scale: float,
    guidance_rescale: float,
    audio_guidance_rescale: float,
    spatio_temporal_guidance_blocks: list[int],
):
    _, encode_video = require_ltx2_diffusers()
    generator = torch.Generator(device="cuda").manual_seed(seed)

    video, audio = pipe(
        image=image,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        frame_rate=frame_rate,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        stg_scale=stg_scale,
        modality_scale=modality_scale,
        guidance_rescale=guidance_rescale,
        audio_guidance_scale=audio_guidance_scale,
        audio_stg_scale=stg_scale,
        audio_modality_scale=modality_scale,
        audio_guidance_rescale=audio_guidance_rescale,
        spatio_temporal_guidance_blocks=spatio_temporal_guidance_blocks,
        use_cross_timestep=True,
        generator=generator,
        output_type="np",
        return_dict=False,
    )
    return video, audio, encode_video


def iter_renderable_shots(data: dict) -> list[tuple[dict, dict]]:
    shots: list[tuple[dict, dict]] = []
    for scene in data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("ltx_mode") == "skip":
                continue
            if not shot.get("ltx_prompt"):
                continue
            shots.append((scene, shot))
    return shots


def build_manifest_entry(
    *,
    scene_id: str,
    shot: dict,
    output_path: Path,
    init_image: Path,
    seed: int,
    num_frames: int,
    frame_rate: float,
) -> dict:
    return {
        "scene_id": scene_id,
        "shot": shot["shot"],
        "type": shot.get("type"),
        "ltx_mode": shot.get("ltx_mode"),
        "use_talking_head_lora": shot.get("use_talking_head_lora"),
        "init_image": str(init_image.relative_to(PROJECT_ROOT)),
        "output": str(output_path.relative_to(PROJECT_ROOT)),
        "seed": seed,
        "num_frames": num_frames,
        "frame_rate": round(frame_rate, 3),
        "duration_seconds": shot.get("duration_seconds"),
        "ltx_prompt": shot.get("ltx_prompt"),
    }


def generate(
    *,
    prompts_path: Path,
    sub_module: str = SUB_MODULE,
    model_id: str,
    talking_head_lora: str,
    talking_head_weight: str,
    talking_head_strength: float,
    hf_home: Path,
    local_files_only: bool,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    seed: int,
    width: int,
    height: int,
    preferred_fps: float,
    max_frames: int,
    num_inference_steps: int,
    guidance_scale: float,
    audio_guidance_scale: float,
    stg_scale: float,
    modality_scale: float,
    guidance_rescale: float,
    audio_guidance_rescale: float,
    spatio_temporal_guidance_blocks: list[int],
    cpu_offload: bool,
    sequential_offload: bool,
    skip_existing: bool,
) -> dict:
    configure_model_cache(hf_home)
    data = json.loads(prompts_path.read_text(encoding="utf-8"))

    out_dir = output_dir(sub_module)
    manifest_path = out_dir / "manifest.json"
    manifest = {
        "story_title": data.get("story_title"),
        "prompts": str(prompts_path.relative_to(PROJECT_ROOT)),
        "model_id": model_id,
        "hf_home": str(hf_home),
        "shots": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pending: list[tuple[dict, dict, Path, Path]] = []
    for scene, shot in iter_renderable_shots(data):
        if scene_ids and scene["scene_id"] not in scene_ids:
            continue
        if shot_numbers and shot["shot"] not in shot_numbers:
            continue

        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        output_path = out_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.mp4"
        if skip_existing and output_path.is_file():
            print(f"Skipping existing {output_path.name}")
            continue

        init_rel = shot.get("init_image")
        if not init_rel:
            raise ValueError(f"{scene_id} shot {shot_num}: missing init_image")
        init_path = PROJECT_ROOT / init_rel
        pending.append((scene, shot, init_path, output_path))

    if not pending:
        print("Nothing to generate.")
        return manifest

    print(f"{len(pending)} LTX shot(s) pending from {prompts_path.name}")
    pipe = load_pipeline(
        model_id=model_id,
        local_files_only=local_files_only,
        cpu_offload=cpu_offload,
        sequential_offload=sequential_offload,
    )

    for scene, shot, init_path, output_path in pending:
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        duration = float(shot.get("duration_seconds") or 5.0)
        num_frames, frame_rate = frames_for_duration(
            duration,
            preferred_fps=preferred_fps,
            max_frames=max_frames,
        )

        configure_talking_head_lora(
            pipe,
            lora_repo=talking_head_lora,
            weight_name=talking_head_weight,
            lora_weight=talking_head_strength,
            enabled=bool(shot.get("use_talking_head_lora")),
        )

        mode = shot.get("ltx_mode", "cinematic")
        print(
            f"Generating {scene_id} shot {shot_num} ({mode}, "
            f"{num_frames} frames @ {frame_rate:.2f} fps) ..."
        )

        image = resolve_init_image(init_path, width, height)
        shot_seed = seed + shot_num + int(scene_id[1:]) * 100
        negative = shot.get("negative_prompt") or DEFAULT_NEGATIVE

        video, audio, encode_video = generate_shot_video(
            pipe,
            image=image,
            prompt=shot["ltx_prompt"],
            negative_prompt=negative,
            width=width,
            height=height,
            num_frames=num_frames,
            frame_rate=frame_rate,
            seed=shot_seed,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            audio_guidance_scale=audio_guidance_scale,
            stg_scale=stg_scale,
            modality_scale=modality_scale,
            guidance_rescale=guidance_rescale,
            audio_guidance_rescale=audio_guidance_rescale,
            spatio_temporal_guidance_blocks=spatio_temporal_guidance_blocks,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        encode_video(
            video[0],
            fps=frame_rate,
            audio=audio[0].float().cpu(),
            audio_sample_rate=pipe.vocoder.config.output_sampling_rate,
            output_path=str(output_path),
        )

        entry = build_manifest_entry(
            scene_id=scene_id,
            shot=shot,
            output_path=output_path,
            init_image=init_path,
            seed=shot_seed,
            num_frames=num_frames,
            frame_rate=frame_rate,
        )
        manifest["shots"] = [
            e
            for e in manifest.get("shots", [])
            if not (e["scene_id"] == scene_id and e["shot"] == shot_num)
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
        description="Generate LTX 2.3 image-to-video clips with native audio from ltx_prompts.json."
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=DEFAULT_PROMPTS,
        help=f"LTX prompts JSON (default: {DEFAULT_PROMPTS.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model id or local diffusers folder.")
    parser.add_argument(
        "--hf-home",
        type=Path,
        default=DEFAULT_HF_HOME,
        help="HF cache root (models download here, not TORCH_HOME).",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Do not download; require model already cached under --hf-home.",
    )
    parser.add_argument(
        "--talking-head-lora",
        default=DEFAULT_TALKING_HEAD_LORA,
        help="HF repo for talking-head AV LoRA.",
    )
    parser.add_argument(
        "--talking-head-weight",
        default=DEFAULT_TALKING_HEAD_WEIGHT,
        help="LoRA safetensors filename inside the repo.",
    )
    parser.add_argument(
        "--talking-head-strength",
        type=float,
        default=0.88,
        help="LoRA strength for talking_head shots.",
    )
    parser.add_argument(
        "--scene",
        action="append",
        dest="scene_ids",
        help="Process only these scene ids. Repeatable.",
    )
    parser.add_argument(
        "--shot",
        type=int,
        action="append",
        dest="shot_numbers",
        help="Process only these shot numbers. Repeatable.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=432)
    parser.add_argument("--preferred-fps", type=float, default=24.0)
    parser.add_argument("--max-frames", type=int, default=257)
    parser.add_argument("--num-inference-steps", type=int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=3.0)
    parser.add_argument("--audio-guidance-scale", type=float, default=7.0)
    parser.add_argument("--stg-scale", type=float, default=1.0)
    parser.add_argument("--modality-scale", type=float, default=3.0)
    parser.add_argument("--guidance-rescale", type=float, default=0.7)
    parser.add_argument("--audio-guidance-rescale", type=float, default=0.7)
    parser.add_argument(
        "--stg-blocks",
        type=int,
        nargs="+",
        default=[28],
        help="Transformer block indices for spatio-temporal guidance.",
    )
    parser.add_argument(
        "--no-cpu-offload",
        action="store_true",
        help="Load full pipeline on GPU (needs lots of VRAM).",
    )
    parser.add_argument(
        "--sequential-offload",
        action="store_true",
        help="Use sequential CPU offload (slowest, least VRAM). Default is model offload.",
    )
    parser.add_argument(
        "--output-sub-module",
        default=SUB_MODULE,
        help=f"Output directory name under output/ (default: {SUB_MODULE}).",
    )
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    if not args.prompts.is_file():
        raise FileNotFoundError(f"Prompts file not found: {args.prompts}")

    width = snap_dim(args.width)
    height = snap_dim(args.height)

    manifest = generate(
        prompts_path=args.prompts,
        sub_module=args.output_sub_module,
        model_id=args.model,
        talking_head_lora=args.talking_head_lora,
        talking_head_weight=args.talking_head_weight,
        talking_head_strength=args.talking_head_strength,
        hf_home=args.hf_home,
        local_files_only=args.local_files_only,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        seed=args.seed,
        width=width,
        height=height,
        preferred_fps=args.preferred_fps,
        max_frames=args.max_frames,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        audio_guidance_scale=args.audio_guidance_scale,
        stg_scale=args.stg_scale,
        modality_scale=args.modality_scale,
        guidance_rescale=args.guidance_rescale,
        audio_guidance_rescale=args.audio_guidance_rescale,
        spatio_temporal_guidance_blocks=args.stg_blocks,
        cpu_offload=not args.no_cpu_offload,
        sequential_offload=args.sequential_offload,
        skip_existing=args.skip_existing,
    )

    print(
        f"Done. {len(manifest.get('shots', []))} shots tracked in "
        f"output/{args.output_sub_module}/manifest.json"
    )


if __name__ == "__main__":
    main()
