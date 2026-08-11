# run_pipeline

Orchestrates the chapter-to-movie pipeline stage by stage.

## Purpose

Director agent entry point: run stages 1–7 in order, enforce gate checks, track state.

## Inputs

- Upstream stage outputs under `output/<sub_module>/`
- Optional passthrough CLI args for each stage script

## Outputs

- `output/pipeline/state.json` — last run status
- `output/pipeline/gates/<stage>.json` — gate pass/fail records

## Usage

```bash
python scripts/run_pipeline.py --dry-run
python scripts/run_pipeline.py --from-stage 1 --to-stage 2
python scripts/run_pipeline.py --from-stage 4 --to-stage 4b -- --backend qwen
```
