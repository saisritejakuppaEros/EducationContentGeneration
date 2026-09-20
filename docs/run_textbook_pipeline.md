# Textbook pipeline (PDF → one video script per unit)

Turn an NCERT / DIKSHA PDF into **one explainer script package per planned video** (directing package, concept bible, screenplay, storyboard). Image/video generation comes later (`--with-pixels` placeholder).

Default cast: [`assets/cartoon/image.png`](../assets/cartoon/image.png) for **M / F / Y** (same character everywhere).

## Prerequisites

1. **LLM** — Qwen via vLLM (see root [readme.md](../readme.md)). Set:

```bash
export OPENAI_API_BASE=http://localhost:8007/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B
```

2. **PDF library** — `pip install pymupdf`

## Default PDF (Assamese Class VII Social Science lesson)

```bash
/workspace/teja/ai_vidya/input/phaseII/assamese/pdfs/diksha/do_3129711180205834241569_ম_নৱ_স_ষ_ট_পৰ_ৱ_শ.pdf
```

## LLM Director (story + full video prep)

After extract + plan + cast, run the **NCERT Explainer Director** (`knowledge/director_skill.md`) on each video unit:

```bash
export OPENAI_API_BASE=http://localhost:8007/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B

# All 3 videos (director → topic bible → screenplay → storyboard)
python3 scripts/run_textbook_director.py \
  --book-id do_3129711180205834241569 \
  --skip-existing \
  --output-root output

# Director + story exports only (faster iteration)
python3 scripts/run_textbook_director.py \
  --book-id do_3129711180205834241569 \
  --video-id v01_rf1 \
  --director-only \
  --output-root output
```

Per video, inputs are built from **chapter + subchapter links** in `manifest.json` → `input/director_brief.md`.

**Language:** All generated scripts (director, screenplay, storyboard) are **English only**. PDF source may be Assamese; the LLM translates for narration while keeping syllabus accuracy.

Outputs under `videos/<video_id>/`:

| Artifact | Purpose |
|----------|---------|
| `directing/directing_package.json` | Beats, VO `script`, `scene_table`, `image_prompts`, `audio_cue_sheet` |
| `directing/story_overview.md` | Beat sheet, turns, title options |
| `directing/vo_script.md` | Readable narration |
| `screenplay/`, `storyboard/` | Production screenplay + shot list (LLM; may lag directing) |
| `shots/shot_decomposition.json` | **Per-shot** Flux captions, VO lines, timing (~10 min default) |
| `shots/shots.md` | Human-readable shot list + narration ready for TTS |
| `shots/narration_manifest.json` | VO-only timeline for audio stage |
| `video_production_package.json` | Index of all paths |

Same flow is also available via `run_textbook_pipeline.py` (full textbook orchestrator).

## Full-timeline BGM (LLM cue sheet + Stable Audio)

When the director’s `audio_cue_sheet` only covers part of the video (e.g. 4:30 of 10:00), plan a new sheet from beats + shot timeline:

```bash
export OPENAI_API_BASE=http://localhost:8007/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B

# Plan → music_cue_sheet.json, then render all cue WAVs (one model load)
python3 scripts/stages/plan_background_music.py \
  --directing-package output/textbooks/.../videos/v01_rf1/directing/directing_package.json \
  --shot-decomposition output/textbooks/.../videos/v01_rf1/shots/shot_decomposition.json \
  --output-root output/textbooks/.../videos/v01_rf1 \
  --and-generate
```

Outputs: `background_audio/music_cue_sheet.json`, `background_audio/cues/M*.wav`, `background_audio/manifest.json`.

## Images + video (Flux keyframes → LTX clips)

Uses `shots/shot_decomposition.json` (not the LLM storyboard). Requires **GPU**, FLUX.2-dev weights, and LTX 2.3 diffusers stack.

```bash
cd /devwork/teja/EducationContentGeneration

# Full unit (~66 keyframes + clips) — long run (use GPU 1 if GPU 0 is busy)
python3 scripts/run_textbook_pixels.py \
  --book-id do_3129711180205834241569 \
  --video-id v01_rf1 \
  --output-root output \
  --gpu 1 \
  --skip-existing

# One scene smoke test
python3 scripts/run_textbook_pixels.py \
  --book-id do_3129711180205834241569 \
  --video-id v01_rf1 \
  --output-root output \
  --scene S01
```

Outputs under `videos/<video_id>/`:

| Path | Purpose |
|------|---------|
| `shots/pixels_storyboard.json` | Flux/LTX-facing shot list |
| `shots/keyframes/<scene>/` | PNG stills |
| `cinematic_videos/cinematic_prompts.json` | LTX prompt manifest |
| `cinematic_videos/` | Generated `.mp4` clips |
| `pixels_manifest.json` | Index |

## Quick start

```bash
cd /devwork/teja/EducationContentGeneration

# 1) Extract + heuristic plan (3 videos for RF 1–3) + cartoon cast — no LLM yet
python3 scripts/run_textbook_pipeline.py \
  --heuristic-plan \
  --through cast \
  --output-root output

# 2) Generate all scripts (needs Qwen vLLM)
python3 scripts/run_textbook_pipeline.py \
  --heuristic-plan \
  --skip-existing \
  --output-root output

# One video only
python3 scripts/run_textbook_pipeline.py \
  --heuristic-plan \
  --video-id v01_rf1 \
  --output-root output
```

Custom PDF:

```bash
python3 scripts/run_textbook_pipeline.py \
  --pdf /path/to/textbook.pdf \
  --book-id my_book_slug \
  --output-root output/run_assamese
```

LLM video grouping (instead of one video per RF section):

```bash
python3 scripts/run_textbook_pipeline.py \
  --pdf /path/to/textbook.pdf \
  --through plan \
  --output-root output
# omit --heuristic-plan so plan_textbook_videos.py runs
```

## Extract chapters first (recommended)

```bash
python3 scripts/stages/extract_textbook_pdf.py \
  --pdf "/path/to/book.pdf" \
  --output-root output
```

Review:

- `output/textbooks/<book_id>/extracted/chapters.md` — human outline  
- `output/textbooks/<book_id>/extracted/chapters.json` — chapter → subchapter tree  
- `manifest.json` — same hierarchy plus flat `sections` (lesson blocks for video planning)

For DIKSHA lesson plans you get **1 chapter (the lesson)** with subchapters:

| Kind | Meaning |
|------|---------|
| `topic` | Section চ) outline bullets |
| `learning_outcome` | Section ছ) formal outcomes |
| `lesson_block` | RF 1/2/3 teaching tables (used for videos) |
| `worksheet` | তাশলকা appendices |

Full NCERT PDFs use heading detection (`Chapter 1`, `1.1`, `পাঠ 2`, …) for multiple chapters.

Re-extract after parser updates: `--force` on `run_textbook_pipeline.py` or delete `manifest.json`.

## Output layout

```
output/textbooks/<book_id>/
  extracted/chapters.md
  extracted/chapters.json
  manifest.json              # metadata + chapters[] + sections[] (video units)
  video_plan.json            # one row per video + chapter_markdown
  series_bible/
    series_bible.json
    reference_photos/M|F|Y/front_neutral.png   # copies of cartoon image
  videos/
    v01_rf1/
      input/chapter.md
      directing/directing_package.json
      math_bible/math_bible.json     # concept bible (social science)
      screenplay/screenplay.json
      storyboard/storyboard.json
```

## Stage scripts (also runnable alone)

| Step | Script |
|------|--------|
| Extract PDF | `scripts/stages/extract_textbook_pdf.py` |
| Plan videos | `scripts/stages/plan_textbook_videos.py` |
| Cartoon cast | `scripts/stages/bootstrap_textbook_cast.py` |
| Concept bible | `scripts/stages/generate_topic_bible.py` |
| Orchestrator | `scripts/run_textbook_pipeline.py` |

Per-chapter **pixel** pipeline reuses existing `run_pipeline.py` with `--output-root` pointing at each `videos/<id>/` (next phase).
