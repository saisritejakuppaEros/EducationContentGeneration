# generate_problem_statement_buildup

Turns a textbook table of contents into a structured sci-fi narrative framework (JSON) where each sub-topic is a story checkpoint.

## Purpose

First step in the textbook-to-movie pipeline: map raw chapter outlines to a cohesive mission narrative as structured data for downstream steps.

## Inputs

- `samples/input_docs.md` — textbook TOC / chapter outline (default)
- `prompts/problem_statement_buildup.md` — system and user prompt template
- `samples/problem_statement_buildup.json` — JSON schema reference (not copied verbatim)
- `gemma4_model/` — local Gemma 4 12B IT weights

## Outputs

All artifacts go under `output/problem_statement_buildup/`:

- `problem_statement_buildup.json` — generated narrative framework

## JSON shape

Top-level keys: `story_title`, `course_flow`, `overarching_problem`, `chapters`, `story_resolution`.

Each chapter has `number`, `name`, `subtitle`, `topics[]`, and `chapter_close` (null for the last chapter).

Each topic has `id`, `topic`, `story_beat`, `why_in_story`.

## Usage

```bash
python scripts/generate_problem_statement_buildup.py
```

Optional flags: `--input`, `--reference`, `--prompt`, `--model-path`, `--output-file`, `--max-new-tokens`, `--disable-thinking`.
