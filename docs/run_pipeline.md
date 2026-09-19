# run_pipeline

Orchestrates the chapter-to-movie pipeline stage by stage.

## Purpose

Director orchestrator: run stages **dir → 1–7** in order, enforce gate checks, track state.

**NCERT explainer mode** uses `scripts/knowledge/director_skill.md` via stage **dir** (`generate_directing_package.py`).

### Priority order (current focus)

1. **Timeline + generation** — `--generation-only` runs **dir → 5a** (skips reference bank 3b and final cut).
2. **Human voice** — stage **6** with `--voice-only` (default in orchestrator): dialogue + math narration TTS only.
3. **Background music** — stage **6b** (`generate_background_audio.py --directing-package`), separate from VO.
4. **Editing / mux** — stage **7** later.
5. **Custom avatars** — stage **3b** when ready (skipped with `--skip-reference-bank`).

## Output location

By default all artifacts go under:

```
output/
  math_bible/
  screenplay/
  series_bible/
  storyboard/
  cinematic_videos/
  manim_videos/
  audio/
  final_cut/
  pipeline/
```

Use `--output-root` to write a full run into a separate folder for A/B comparison:

```bash
python scripts/run_pipeline.py --output-root output/run_a --from-stage 1 --to-stage 4
python scripts/run_pipeline.py --output-root output/run_b --from-stage 1 --to-stage 4
```

Every stage script also accepts `--output-root` (or set `PIPELINE_OUTPUT_ROOT` env var).

## Inputs

- Upstream stage outputs under `<output-root>/<sub_module>/`
- Optional passthrough CLI args for each stage script

## Outputs

- `<output-root>/pipeline/state.json` — last run status
- `<output-root>/pipeline/gates/<stage>.json` — gate pass/fail records

## Usage

```bash
python scripts/run_pipeline.py --dry-run
python scripts/run_pipeline.py --generation-only
python scripts/run_pipeline.py --output-root output/experiment_01 --from-stage dir --to-stage 4
python scripts/run_pipeline.py --from-stage 4 --to-stage 4b -- --backend qwen
python scripts/run_pipeline.py --from-stage 6 --to-stage 6b
```

### Manim toggle (stage 5b)

By default Manim is **off**: stage 5b is skipped and MATH INSERT / CONCEPT shots are rendered as cinematic LTX (stages 4b and 5a pass `--include-math-inserts`). Final assembly uses those clips unless you opt in to Manim.

```bash
# Default — no Manim, full video via LTX + keyframes
python scripts/run_pipeline.py --from-stage 4b --to-stage 7

# Optional Manim math inserts (skips LTX for those shots)
python scripts/run_pipeline.py --enable-manim --from-stage 5b --to-stage 7
```

Compare two runs:

```bash
diff -ru output/run_a/storyboard/storyboard.json output/run_b/storyboard/storyboard.json
ls output/run_a/final_cut/ output/run_b/final_cut/
```
