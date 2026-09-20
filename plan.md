# Chapter-to-Movie: Multi-Agent Pipeline (Implementation Plan)

**Input:** one textbook chapter (table of contents + sub-topics, or full chapter text).  
**Output:** one science-fiction short film that teaches that chapter, dubbed in multiple Indian languages.

**Cast (locked):** M (Mathematician), F (Friend), Y (You — viewer POV).

**Core law:** M poses the real problem → Y and F work it out → F teaches Y via cinematic scenes → one high-level Manim insert per concept → back to story.

This plan follows [coding_agent_prompts/skills.md](coding_agent_prompts/skills.md):

| Rule | Convention |
|------|--------------|
| Python | `scripts/` only |
| Documentation | `docs/` — one short file per script |
| Generated artifacts | `output/<sub_module_name>/` only |
| Shared helpers | `scripts/paths.py`, `scripts/gemma_utils.py`, `scripts/qwen_utils.py` |
| Prompts & samples | `scripts/prompts/`, `scripts/samples/` (existing pattern) |

Implement **one step at a time**. Do not start GPU-heavy stages until all upstream text stages pass their gates.

---

## Pipeline at a glance

```
Chapter Text
  → [1] topic_specs          (text)
  → [2] screenplay          (text)
  → [3] series_profile        (text + reference photos)
  → [4] storyboard          (text + keyframe stills)
  → [5a] cinematic_videos   (WAN/LTX pixels)     ┐
  → [5b] manim_videos       (Manim pixels)        ├ parallel after stage 4
  → [6] audio               (voice / sfx / dub)   │
  → [7] final_cut           (ffmpeg assembly)  ◀──┘
```

Each stage has a **gate**: a review pass before the next stage runs. Text gates use Qwen 3.6; visual gates use Gemma 4.

---

## Step 0 — Project bootstrap

**Goal:** shared infrastructure every later script reuses.

| Deliverable | Path |
|-------------|------|
| Output helper | `scripts/paths.py` (exists) |
| Director orchestrator | `scripts/run_pipeline.py` |
| Director doc | `docs/run_pipeline.md` |
| Pipeline state | `output/pipeline/state.json` |

**`run_pipeline.py` responsibilities**

- Accept `--chapter`, `--from-stage`, `--to-stage`.
- Load gate results; block downstream stages on failure.
- Never write artifacts outside `output/<sub_module>/`.

**Gate:** manual smoke test — `python scripts/run_pipeline.py --dry-run` lists stages and expected I/O paths.

---

## Step 1 — Mathematician Agent

**Goal:** extract sub-topics, invent load-bearing real-world problems, lock equations and Manim scope.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/generate_math_specs.py` |
| Prompt | `scripts/prompts/math_specs.md` |
| Sample schema | `scripts/samples/math_specs.json` |
| Doc | `docs/generate_math_specs.md` |
| Output | `output/math_specs/math_specs.json` |

**Input**

```json
{
  "chapter_text": "raw chapter or ToC + subtopics",
  "series_profile_math_history": "concepts taught in prior chapters (empty on chapter 1)"
}
```

**Output shape — `math_specs.json`**

```json
{
  "chapter": "Complex Numbers",
  "topics": [
    {
      "id": "1.1",
      "topic": "Complex numbers as ordered pairs",
      "real_world_problem": "concrete situation",
      "equation": "z = a + ib",
      "why_this_tool": "string",
      "prerequisites": [],
      "core_visual_idea": "ONE thing the Manim insert must show",
      "explicitly_excluded": ["formal field axioms", "polar form derivation"]
    }
  ]
}
```

**Gate:** second independent Qwen call re-verifies every equation; failed topics get a targeted fix, not a full regeneration.

**Replaces (old pipeline):** `generate_ps_math_linkup.py` — richer schema, correctness gate, Manim scope locked here.

**Run**

```bash
python scripts/stages/generate_math_specs.py \
  --input scripts/samples/input_docs.md \
  --output-file output/math_specs/math_specs.json
```

---

## Step 2 — Screenwriter Agent

**Goal:** turn `math_specs.json` into a real screenplay — scenes, action lines, dialogue, intentions.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/generate_screenplay.py` |
| Prompt | `scripts/prompts/screenplay.md` |
| Sample schema | `scripts/samples/screenplay.json` |
| Doc | `docs/generate_screenplay.md` |
| Output | `output/screenplay/screenplay.json`, `output/screenplay/screenplay.md` |

**Input**

```json
{
  "topic_specs": "output/math_specs/math_specs.json",
  "series_profile": "output/series_profile/series_profile.json (empty on chapter 1)",
  "chapter_runtime_target_minutes": 18
}
```

**Scene types:** `STORY` (cinematic), `CONCEPT` (Manim), `HYBRID` (diegetic screen → Manim).

**Output shape — `screenplay.json`**

```json
{
  "chapter": "Complex Numbers",
  "scenes": [
    {
      "scene_id": "SC03",
      "type": "STORY",
      "int_ext": "INT",
      "location": "Control Room",
      "time_of_day": "NIGHT",
      "topic_ids": ["1.1"],
      "action": "action lines",
      "dialogue": [
        {"character": "M", "line": "We're picking up something. It's not noise — it's repeating."}
      ],
      "target_duration_seconds": 60,
      "leads_to": "SC04"
    }
  ]
}
```

**Gate:** every `topic_specs` topic covered; F never explains before Y has a reason to need it; dialogue WPM plausible for target duration; rising tension, not flat lessons.

**Replaces (old pipeline):** `generate_problem_statement_buildup.py` + narrative beats from `generate_image_video_generation.py`.

**Run**

```bash
python scripts/stages/generate_screenplay.py \
  --topic-specs output/math_specs/math_specs.json \
  --output-dir output/screenplay
```

---

## Step 3 — Character & Series Profile Agent

**Goal:** lock M/F/Y identity, voice, world, visual grammar, and a multi-angle reference photo bank.

| Deliverable | Path |
|-------------|------|
| Script (series profile) | `scripts/stages/generate_series_profile.py` |
| Script (photo bank) | `scripts/stages/build_reference_bank.py` |
| Prompts | `scripts/prompts/series_profile.md`, `scripts/prompts/reference_bank.md` |
| Sample schema | `scripts/samples/series_profile.json` |
| Doc | `docs/generate_series_profile.md`, `docs/build_reference_bank.md` |
| Output | `output/series_profile/series_profile.json` |
| Reference photos | `output/series_profile/reference_photos/{M,F,Y}/` |

**Reference bank tags (minimum per character)**

| Tag | Purpose |
|-----|---------|
| `front_neutral` | primary identity anchor |
| `three_quarter_left`, `three_quarter_right` | OTS / two-shot |
| `profile` | walk-and-talk, silhouette |
| `close_up_neutral` | INSERT / REACTION |
| `close_up_expression_*` | 2–3 expression variants |
| `wide_full_body_neutral_pose` | true wide shots |

**Build once, lock before chapter production.** Extend the bank only when a new angle is needed — never ad hoc mid-chapter.

**Output shape — `series_profile.json`**

```json
{
  "cast": {
    "M": {
      "role": "Mathematician",
      "description": "...",
      "voice_profile": {},
      "reference_photos": [
        {"tag": "front_neutral", "path": "output/series_profile/reference_photos/M/front_neutral.png"}
      ]
    },
    "F": {},
    "Y": {}
  },
  "world": {"premise": "...", "sets": []},
  "visual_grammar": {"grade": "...", "camera_rules": [], "screen_direction_rules": "..."},
  "chapters_so_far": [{"chapter": 1, "arc_delta": "...", "callbacks_available": []}]
}
```

**Gate:** manual review of reference bank (cheap — handful of images); series profile reviewed for cast/world consistency.

**Replaces (old pipeline):** implicit cast from `person/` single photos — now asset-managed under `output/series_profile/`.

**Run**

```bash
python scripts/stages/generate_series_profile.py --output-dir output/series_profile
python scripts/stages/build_reference_bank.py \
  --source person/ \
  --output-dir output/series_profile/reference_photos
```

---

## Step 4 — Storyboard / Image Agent

**Goal:** break each scene into fully specified shots; generate keyframe stills with multi-reference Flux.

| Deliverable | Path |
|-------------|------|
| Script (shot breakdown) | `scripts/stages/generate_storyboard.py` |
| Script (keyframes) | `scripts/stages/generate_storyboard_keyframes.py` |
| Prompts | `scripts/prompts/storyboard.md`, `scripts/prompts/storyboard_keyframe.md` |
| Sample schema | `scripts/samples/storyboard.json` |
| Doc | `docs/generate_storyboard.md`, `docs/generate_storyboard_keyframes.md` |
| Output (JSON) | `output/storyboard/storyboard.json` |
| Output (images) | `output/storyboard/<scene_id>/<scene_id>_shot##.png` |

**Required shot fields (all mandatory)**

- `type`, `lens_mm`, `subject_scale_pct`, `camera_move`
- `characters_in_frame` + `reference_tags_used` (lookup from series profile bank)
- `environment_detail`, `blocking`, `dialogue` (single speaker)
- `duration_seconds`, `keyframe_image`, `qc_status`

**Coverage rules**

- Every scene: at least one true WIDE (`subject_scale_pct` ≤ 30%) before medium/close.
- Floor per scene: one wide, one medium, one close.
- `HYBRID` scenes end on push-in toward screen/device (match-cut into Manim).

**Sub-steps**

1. **4a** — Qwen shot breakdown (text only).
2. **4b** — deterministic reference-bank tag selection per shot.
3. **4c** — FLUX.2-dev keyframe generation via `Flux2Pipeline` (multi-reference + optional mask compositing).
4. **4d** — Gemma 4 visual QC; localized mask retry on failure.

### 4c — Keyframe generation (`Flux2Pipeline`, multi-reference + mask)

Model: `black-forest-labs/FLUX.2-dev` (~80 GB VRAM BF16, or 4-bit quant). Same pipeline family as `generate_flux_images.py`, extended to multiple reference images and mask-based surgical fixes.

```python
import torch
from diffusers import Flux2Pipeline
from PIL import Image

repo_id = "black-forest-labs/FLUX.2-dev"
pipe = Flux2Pipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16)
pipe.to("cuda")

# image[0] = base plate: set reference or previous shot in this scene (continuity)
# image[1] = character ref from bank (tag-selected in 4b)
# image[2] = second character ref, if two-shot
base_plate = Image.open(set_reference_path)
ref_char_a = Image.open(bank_lookup("M", "wide_full_body_neutral_pose"))
ref_char_b = Image.open(bank_lookup("F", "three_quarter_left"))

prompt = (
    "wide establishing shot, 24mm lens: the mathematician from image two standing at the "
    "secondary console with the cracked display, the friend from image three entering frame "
    "left, control room from image one, dish-array status board visible on the back wall, "
    "teal shadows, warm amber highlights, anamorphic flare off the screens"
)

output = pipe(
    image=[base_plate, ref_char_a, ref_char_b],
    prompt=prompt,
    num_inference_steps=28,   # 50 for max quality; 28 is the speed/quality trade-off
    guidance_scale=4.0,
)
output.images[0].save(keyframe_output_path)
```

**Mask-based retry** (when 4d QC flags one region — face, wardrobe — in an otherwise-good frame):

```python
mask = build_mask(region="face", frame_size=output.images[0].size)  # white = edit region

output_fixed = pipe(
    image=[output.images[0], ref_char_a],
    prompt="the mathematician's face from image two, matching identity exactly",
    mask_image=mask,
    num_inference_steps=28,
    guidance_scale=4.0,
)
```

New sets get their reference plate generated once (no character refs) and saved to `series_profile.world.sets[].reference_image` for reuse across chapters.

**Gate:** Director contact-sheet review per scene; wide-shot coverage rule enforced.

**Replaces (old pipeline):** `generate_image_video_generation.py` + `generate_flux_prompts.py` + `generate_flux_images.py`.

**Run**

```bash
python scripts/stages/generate_storyboard.py \
  --screenplay output/screenplay/screenplay.json \
  --series-profile output/series_profile/series_profile.json \
  --output-dir output/storyboard

python scripts/stages/generate_storyboard_keyframes.py \
  --storyboard output/storyboard/storyboard.json \
  --skip-existing
```

---

## Step 5a — Cinematic Video Agent

**Goal:** animate every `STORY` / `HYBRID` shot from its keyframe.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/generate_cinematic_videos.py` |
| Prompt | `scripts/prompts/cinematic_video.md` |
| Doc | `docs/generate_cinematic_videos.md` |
| Output | `output/cinematic_videos/<scene_id>/<scene_id>_shot##.mp4` |
| Manifest | `output/cinematic_videos/manifest.json` |

**Guardrails**

- One speaking character per shot (dialogue pre-split at Step 2).
- Stage 5a audio is lip-sync reference only; final voice comes from Step 6.
- Motion continues from previous shot's implied end state.

**Replaces (old pipeline):** `generate_ltx_prompts.py` + `generate_ltx_videos.py`.

**Run**

```bash
export OPENAI_API_BASE=http://localhost:8000/v1
python scripts/stages/generate_cinematic_videos.py --scene SC03 --skip-existing
```

---

## Step 5b — Math Insert Agent (Manim)

**Goal:** one high-level visual per topic — `core_visual_idea` only, no derivations.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/generate_manim_videos.py` (adapt existing) |
| Doc | `docs/generate_manim_videos.md` (update) |
| Output | `output/manim_videos/<topic_id>.mp4` |
| Source | `output/manim_videos/<topic_id>.py` |

**Hard rule:** visualize `topic_specs.topics[].core_visual_idea` only. Scope creep = Stage 1 problem, not Manim problem.

**Generation loop:** Qwen writes code → render → Gemma 4 visual review + code review → fix until pass (cap N cycles).

**Run**

```bash
source .venv/bin/activate
python scripts/stages/generate_manim_videos.py \
  --topic-specs output/math_specs/math_specs.json \
  --topic 1.1
```

---

## Step 6 — Audio Agent

**Goal:** lock timing, voice identity, sound design, score, multilingual dubbing.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/generate_audio.py` |
| Prompts | `scripts/prompts/audio_timing.md`, `scripts/prompts/audio_dubbing.md` |
| Doc | `docs/generate_audio.md` |
| Output | see layout below |

**Sub-steps (run in order)**

1. **6.1 Timing pass** — dry TTS / WPM model; reconcile durations across screenplay → storyboard → video.
2. **6.2 Voice performance** — one voice clone per character (created at Step 3 setup), reused forever.
3. **6.3 Sound design & score** — scene ambience beds, foley, recurring sonic motif.
4. **6.4 Multilingual dubbing** — Gemma 4 localizes dialogue; same voice identity per character per language.

**Output layout**

```
output/audio/
  source/<scene_id>_<shot>.wav
  sfx/<scene_id>.wav
  score/<chapter>_cue##.wav
  dub/<lang_code>/<scene_id>_<shot>.wav
  subtitles/<lang_code>/<chapter>.srt
```

**Gate:** every dialogue line fits its shot duration after 6.1 lock.

---

## Step 7 — Editor Agent

**Goal:** assemble all assets into one film per language.

| Deliverable | Path |
|-------------|------|
| Script | `scripts/stages/assemble_final_cut.py` |
| Doc | `docs/assemble_final_cut.md` |
| Output | `output/final_cut/<chapter_title>_<lang>.mp4`, `output/final_cut/<chapter_title>.edl` |

**Assembly steps**

1. Concatenate shots in `storyboard.json` order (5a + 5b).
2. Apply shared LUT from `series_profile.visual_grammar.grade`.
3. Match-cut Manim inserts via planned push-in/pull-back shots.
4. Mux locked voice (6.2), sfx bed (6.3), score (6.3).
5. Repeat mux per language (6.4 dub + subtitles).
6. Write EDL for manual tweaks without re-generation.

**Final gate:** end-to-end review against screenplay intent and `topic_specs` topic coverage.

**Run**

```bash
python scripts/stages/assemble_final_cut.py \
  --storyboard output/storyboard/storyboard.json \
  --languages en,hi,ta
```

---

## Model routing

| Task | Model |
|------|-------|
| Orchestration, gates, math, screenplay, specs, shot breakdown, Manim code, audio planning | Qwen 3.6 (vLLM) |
| Keyframe QC, Manim visual review, dubbing / localization | Gemma 4 |
| Keyframe pixels | FLUX.2-dev via `Flux2Pipeline` (multi-reference + mask inpaint) |
| Cinematic video | WAN 2.2-class / LTX (existing) |
| Math render | Manim |
| Voice / TTS | dedicated voice-clone model |
| Assembly | ffmpeg (deterministic) |

**Rule:** Qwen plans and judges. Gemma looks at pixels and handles Indian-language fluency. GPU generation runs last.

---

## Migration map (old → new)

| Old script | New script | New output dir |
|------------|------------|----------------|
| `generate_problem_statement_buildup.py` | `generate_screenplay.py` | `output/screenplay/` |
| `generate_ps_math_linkup.py` | `generate_math_specs.py` | `output/topic_specs/` |
| `generate_image_video_generation.py` | `generate_storyboard.py` | `output/storyboard/` |
| `generate_flux_prompts.py` + `generate_flux_images.py` | `generate_storyboard_keyframes.py` | `output/storyboard/` |
| `generate_ltx_prompts.py` + `generate_ltx_videos.py` | `generate_cinematic_videos.py` | `output/cinematic_videos/` |
| `generate_manim_videos.py` | same (adapt inputs) | `output/manim_videos/` |
| *(missing)* | `generate_series_profile.py` | `output/series_profile/` |
| *(missing)* | `generate_audio.py` | `output/audio/` |
| *(missing)* | `assemble_final_cut.py` | `output/final_cut/` |

Old scripts remain until each new step is verified. Remove only after the replacement passes its gate.

---

## Implementation order (follow one by one)

| Order | Step | Blocked by | GPU? |
|-------|------|------------|------|
| 0 | Bootstrap (`run_pipeline.py`) | — | No |
| 1 | `generate_math_specs.py` | Step 0 | No |
| 2 | `generate_screenplay.py` | Step 1 gate | No |
| 3 | `generate_series_profile.py` + `build_reference_bank.py` | Step 2 gate | Photos only |
| 4 | `generate_storyboard.py` + `generate_storyboard_keyframes.py` | Step 3 gate | Yes (Flux) |
| 5a | `generate_cinematic_videos.py` | Step 4 gate | Yes (LTX/WAN) |
| 5b | `generate_manim_videos.py` (adapt) | Step 1 gate | Yes (Manim) |
| 6 | `generate_audio.py` | Steps 5a + 5b | Yes (TTS) |
| 7 | `assemble_final_cut.py` | Step 6 gate | No (ffmpeg) |

Steps 5a and 5b can run in parallel once Step 4 passes.

---

## Per-step checklist (every new script)

1. Write working code in `scripts/`.
2. Add prompt template in `scripts/prompts/` and sample schema in `scripts/samples/`.
3. Add short doc in `docs/` (purpose, inputs, outputs, usage).
4. Save all artifacts under `output/<sub_module_name>/`.
5. Wire stage into `run_pipeline.py` with gate hook.
6. Run gate before starting the next step.

---

## Why this fixes "doesn't feel like a movie"

- A **screenplay** exists before any shots — dialogue has intention, scenes have arcs.
- **Y has a face and voice**; cast is asset-managed as a reference bank, not one headshot.
- **Wide shots are required**, not optional — lens, scale, and environment are specified.
- **Math inserts are capped to one idea** by the Mathematician Agent, not hoped for at render time.
- **Voice identity is locked** once per character; dubbing is N audio layers on one picture cut.
- **An Editor stage assembles the film** — without Step 7, there are only clips in folders.
