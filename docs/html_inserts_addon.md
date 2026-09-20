# HTML diagram inserts (optional addon)

HTML/CSS/JS inserts are an **optional addon** for diagram-heavy shots. They do **not** replace the default pipeline (Flux keyframes + I2V clips). Manim (stage **5b**) remains available the same way.

## Three ways to render “insert” shots

| Mode | Flag | Stage | When to use |
|------|------|-------|-------------|
| **Default** | *(none)* | 4b + 5a with `--include-math-inserts` | Explainer look; no extra tooling |
| **Manim** | `--enable-manim` | 5b | Equation-heavy math, legacy manim-generator |
| **HTML** | `--enable-html-inserts` | 5h | Maps, timelines, mechanisms, social-science diagrams |

**Mux priority** (stage 7): for `MATH INSERT` / `CONCEPT` shots, if `--enable-html-inserts` and an HTML MP4 exists → use it; else if `--enable-manim` and Manim MP4 exists → use it; else **LTX / keyframe fallback**.

You can enable **both** Manim and HTML; HTML wins when both produced a clip for the same shot.

## Stage 5h — `render_html_inserts.py`

**Outputs:** `html_inserts/<scene_id>/<scene_id>_shotNN.mp4`, `html_inserts/manifest.json`

**Inputs (either or both):**

- `storyboard/storyboard.json` — chapter pipeline (`MATH INSERT`, `CONCEPT`)
- `shots/shot_decomposition.json` — textbook pipeline (`visual_mode`: map, mechanism, diagram, …)

**Authoring HTML**

Place a self-contained page at:

```
html_inserts/<scene_id>/<scene_id>_shotNN/index.html
```

Animations can use CSS, SVG, GSAP, D3, etc. Keep assets inline or relative paths under that folder.

**Stub generation** (placeholder slide until you replace with real HTML):

```bash
python3 scripts/stages/render_html_inserts.py \
  --output-root output/textbooks/<book_id>/videos/<video_id> \
  --generate-stubs --skip-existing
```

**Recording** requires Playwright + Chromium:

```bash
pip install playwright
playwright install chromium
```

Then run stage 5h via orchestrator or directly:

```bash
python3 scripts/run_pipeline.py \
  --output-root "$RUN" \
  --enable-html-inserts \
  --from-stage 5h --to-stage 5h

python3 scripts/run_pipeline.py \
  --output-root "$RUN" \
  --enable-html-inserts \
  --from-stage 7 --to-stage 7 \
  --skip-reference-bank
```

## Textbook + `math_bible.json`

Topic-level visual briefs (e.g. `core_visual_idea` in `math_bible/math_bible.json`) are a good source for hand-written or LLM-generated HTML. There is **no automatic LLM→HTML step yet**; workflow today:

1. Pick shots from `shot_decomposition.json` (map/mechanism scenes).
2. Write `index.html` per shot (or use `--generate-stubs` for layout tests).
3. Run **5h**, then mux with `--enable-html-inserts`.

A future **5h-generate** sub-step could call Qwen to emit HTML from `core_visual_idea` + series palette without changing default LTX behavior.

## Default behavior unchanged

`run.sh` and textbook pixels **do not** enable HTML or Manim. Existing runs keep using MiniMax/LTX for all shots unless you opt in.
