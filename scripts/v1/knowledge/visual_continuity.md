# Visual continuity (keyframes + clips)

Use with `generate_storyboard_keyframes.py` and `generate_cinematic_videos.py`.

## Reference photos

1. Run **stage 3b** / `build_reference_bank.py` so each cast key has `front_neutral`, `close_up_neutral`, `wide_full_body_neutral_pose`, and at least one three-quarter tag — not copy-only duplicates.
2. Storyboard shots must set `reference_tags_used` when framing differs (close-up vs wide).
3. Do **not** use the mascot PNG as the **environment** reference; backgrounds come from `flux_prompt` only.
4. At most **two** character refs per keyframe; pick tags via shot type (`pick_reference_tag` in code).

## Keyframe pass

- Enable **mask retry** for any shot with characters (face inpaint from bank close-up).
- Prior shot is optional future work; for now rely on bank + indexed Flux prompts.

## Clips

- I2V always uses the keyframe as `init_image`; fix identity in Flux before video gen.
- Prefer local MiniMax-H3 or LTX with speech in **separate TTS**, not model-native VO drift.
