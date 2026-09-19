# generate_ps_math_linkup

Maps each story checkpoint to the exact math equation that solves it (Problem → Equation → Why).

## Purpose

Stage 2 of the textbook-to-movie pipeline: take the narrative framework from stage 1 and attach the correct formulas for scene staging.

## Inputs

- `output/problem_statement_buildup/problem_statement_buildup.json` — stage 1 output (default)
- `prompts/ps_math_linkup.md` — system and user prompt template
- `samples/ps_math_linkup.json` — JSON schema reference
- `gemma4_model/` — local Gemma 4 12B IT weights

## Outputs

All artifacts go under `output/ps_math_linkup/`:

- `ps_math_linkup.json` — structured math linkup per sub-topic

## JSON shape

Top-level keys: `story_title`, `description`, `usage_note`, `chapters`.

Each topic has `id`, `topic`, `problem`, `equation` (LaTeX), `why_equation`.

## Usage

```bash
python scripts/legacy/generate_ps_math_linkup.py
```

Optional flags: `--input`, `--reference`, `--prompt`, `--model-path`, `--output-file`, `--max-new-tokens`, `--disable-thinking`.
