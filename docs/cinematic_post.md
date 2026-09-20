# Cinematic post-production (QC, pacing, final cut)

## Reference pacing (copy hook / cut rhythm)

Analyze a reference YouTube-style clip or any local MP4, then retime the storyboard before keyframes:

```bash
# URL (requires yt-dlp) or local file
python3 scripts/stages/analyze_reference_pacing.py \
  --output-root output/textbooks/<book>/videos/<run> \
  --input "https://www.youtube.com/shorts/...."

python3 scripts/stages/apply_pacing_profile.py \
  --output-root output/textbooks/<book>/videos/<run> \
  --dry-run

python3 scripts/stages/apply_pacing_profile.py \
  --output-root output/textbooks/<book>/videos/<run>
```

Profile: `<output-root>/pipeline/reference_pacing_profile.json`  
Backup: `storyboard/storyboard.pre_pacing.json`

## Production QC + contact sheet

After stage **5a** (cinematic videos):

```bash
python3 scripts/stages/validate_production_assets.py \
  --output-root output/textbooks/<book>/videos/<run> \
  --fail-on-error
```

Outputs:

- `pipeline/qc_report.json` — ffprobe validation, director checklist, per-shot scores
- `pipeline/contact_sheet.html` — filmstrip for human review

Storyboard ids `SC01` are matched to on-disk folders `S01` automatically.

## Final cut (cinematic grade + VO + BGM + captions)

```bash
python3 scripts/stages/assemble_final_cut.py \
  --output-root output/textbooks/<book>/videos/<run> \
  --max-clips 8

# Full run (after stages 6 / 6b)
python3 scripts/run_pipeline.py \
  --output-root output/textbooks/<book>/videos/<run> \
  --from-stage 5c --to-stage 7
```

Flags:

- `--no-cinematic-grade` — skip contrast/saturation and shot fades
- `--no-audio-mix` — video-only concat
- `--bgm-volume 0.18` — duck background music under narration

Pipeline stages: **ref** → **4p** → **5c** → **7** (see `scripts/README.md`).
