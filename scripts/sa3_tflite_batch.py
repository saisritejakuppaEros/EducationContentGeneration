#!/usr/bin/env python3
"""Multiple SA3 TFLite jobs in one process — load DiT + decoder once, reuse via set_conditioning."""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TFLITE_ROOT = PROJECT_ROOT / ".stable-audio-tflite"
if not TFLITE_ROOT.is_dir():
    sys.exit(f"Stable Audio TFLite not installed: {TFLITE_ROOT} (run scripts/setup_stable_audio.sh)")

sys.path.insert(0, str(TFLITE_ROOT))
sys.path.insert(0, str(TFLITE_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("sa3_tflite", TFLITE_ROOT / "scripts" / "sa3_tflite.py")
sa3 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(sa3)

from weights import dec_rel, dit_rel, ensure_local, is_present  # noqa: E402


def _encode_cfg_branch(t5, tok, cfg: float, negative_prompt: str | None):
    null_h = null_m = None
    if cfg == 1.0:
        return null_h, null_m
    if negative_prompt:
        n_ids, n_mask = tok(negative_prompt)
        null_h = t5(n_ids, n_mask)
        null_m = n_mask.astype(np.float32)
    else:
        null_h = np.zeros((1, sa3.COND_TOKENS, sa3.COND_DIM), np.float32)
        null_m = np.zeros((1, sa3.COND_TOKENS), np.float32)
    return null_h, null_m


def run_batch(
    jobs: list[dict],
    *,
    dit: str,
    decoder: str,
    dit_precision: str = "fp32",
    decoder_precision: str = "w8a8",
    cfg: float = 2.0,
    apg: float = 1.0,
    steps: int = 8,
    threads: int = 8,
    cfg_batched: bool = True,
    default_negative: str | None = None,
    skip_existing: bool = False,
) -> None:
    dec = decoder or sa3.DEFAULT_DECODER[dit]
    pending = [
        j
        for j in jobs
        if not (skip_existing and Path(j["out"]).is_file())
    ]
    if not pending:
        print(f"All {len(jobs)} job(s) already exist — nothing to generate.")
        return

    for rel in (sa3.T5_REL, dit_rel(dit, dit_precision), dec_rel(dec, decoder_precision)):
        if not is_present(rel):
            ensure_local(rel)

    print(f"\nSA3 batch: {len(pending)} job(s) — load models once (dit={dit}, decoder={dec})\n")
    t_wall = time.perf_counter()

    tok = sa3.P.Tokenizer()
    t5 = sa3.P.T5GemmaTFLite(ensure_local(sa3.T5_REL), threads)
    dit_path = ensure_local(dit_rel(dit, dit_precision))
    decoder_obj = sa3.RungDecoder(
        ensure_local(dec_rel(dec, decoder_precision)),
        threads=threads,
        trim=sa3.RUNG_TRIM[dec],
        max_rung=None,
    )
    backend: sa3.BakedDiT | None = None

    for idx, job in enumerate(jobs, start=1):
        out_path = Path(job["out"])
        if skip_existing and out_path.is_file():
            print(f"[{idx}/{len(jobs)}] skip existing {out_path.name}")
            continue

        prompt = job["prompt"]
        seconds = float(job["seconds"])
        seed = int(job["seed"]) if job.get("seed") is not None else random.randint(0, 2**31 - 1)
        neg = job.get("negative_prompt") or default_negative
        T_lat = sa3.valid_T_lat(seconds)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{idx}/{len(jobs)}] {seconds:.1f}s → {out_path.name}")

        ids, mask = tok(prompt)
        t5_hidden = t5(ids, mask)
        null_h, null_m = _encode_cfg_branch(t5, tok, cfg, neg)

        if backend is None:
            backend = sa3.BakedDiT(
                dit_path,
                T_lat,
                t5_hidden,
                mask.astype(np.float32),
                seconds,
                threads=threads,
                cfg=cfg,
                apg=apg,
                null_hidden=null_h,
                null_mask=null_m,
                batched=cfg_batched,
            )
        else:
            backend.set_conditioning(
                T_lat,
                t5_hidden,
                mask.astype(np.float32),
                seconds,
                cfg=cfg,
                apg=apg,
                null_hidden=null_h,
                null_mask=null_m,
                batched=cfg_batched,
            )

        x0, step_noise = sa3.P.make_noise(T_lat, steps, seed)
        sig = sa3.P.build_pingpong_schedule(steps, 1.0)
        latents = sa3.P.sample(backend, x0, step_noise, sig, None, None)

        dec_lat = latents
        if dec == "same-s" and T_lat % 2:
            dec_lat = np.concatenate([latents, latents[:, :, -1:]], axis=2)
        audio = decoder_obj.decode(dec_lat)[:, :, : T_lat * sa3.SAMPLES_PER_LATENT]
        audio_np = audio[0]
        req = int(round(seconds * sa3.SAMPLE_RATE))
        if audio_np.shape[-1] > req:
            audio_np = audio_np[:, :req]
        sa3.P.save_wav(str(out_path), audio_np)

    del backend, decoder_obj, t5
    sa3._free()
    elapsed = time.perf_counter() - t_wall
    print(f"\nBatch done in {elapsed:.1f}s wall ({len(jobs)} jobs)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SA3 TFLite batch generation (single model load).")
    parser.add_argument("--jobs", type=Path, required=True, help="JSON list of {prompt, out, seconds, seed?}")
    parser.add_argument("--dit", default="sm-music")
    parser.add_argument("--decoder", default="same-s")
    parser.add_argument("--cfg", type=float, default=2.0)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    if not isinstance(jobs, list) or not jobs:
        raise SystemExit("--jobs must be a non-empty JSON array")

    run_batch(
        jobs,
        dit=args.dit,
        decoder=args.decoder,
        cfg=args.cfg,
        steps=args.steps,
        threads=args.threads,
        default_negative=args.negative_prompt,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
