# generate_directing_package

Runs the **NCERT Explainer Director** skill (`scripts/knowledge/director_skill.md`) to produce a timeline-first directing package for downstream generators.

## Purpose

Stage **dir** — not the renderer. Outputs beat sheet, VO script with timestamps, scene table, image prompts, and **BGM cue sheet** (for Stable Audio, not TTS).

## Inputs

- Chapter text (default: `scripts/samples/input_docs.md`)
- Director skill: `scripts/knowledge/director_skill.md`

## Outputs

```
output/directing/
  directing_package.json
  directing_timeline.md
output/pipeline/gates/directing_package.json
```

## Usage

```bash
python scripts/stages/generate_directing_package.py --backend qwen
python scripts/stages/generate_directing_package.py --input path/to/chapter.md --runtime-seconds 480
```

## Orchestration

```bash
# Timeline + video generation first (no final cut, no reference bank)
python scripts/run_pipeline.py --generation-only --backend qwen

# Human VO only in stage 6; BGM in stage 6b
python scripts/run_pipeline.py --from-stage 6 --to-stage 6b
python scripts/stages/generate_background_audio.py --directing-package
```

Custom mascots and cast reference photos stay in stage **3b** until you drop `--skip-reference-bank`.
