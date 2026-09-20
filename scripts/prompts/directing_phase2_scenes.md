# System

NCERT explainer director — **phase 2: scene_table batch only**. Output JSON: `{"scene_table": [...]}` only.

# User

Runtime {{runtime_seconds}}s. This batch: scenes **{{batch_start_id}}** through **{{batch_end_id}}** (exactly **{{batch_count}}** scenes).

Prior beats (reference):
```json
{{beat_sheet_json}}
```

Prior script (reference):
```json
{{script_json}}
```

{{continuation_note}}

Each scene object:
```json
{
  "scene_id": "S01",
  "time_start": "0:00",
  "duration_seconds": 12,
  "vo_excerpt": "max 8 words",
  "visual_mode": "illustrated | diagram | anchor | map | text_card",
  "anchor_present": true,
  "on_screen_text": "max 5 words",
  "motion": "short phrase",
  "sfx_note": "optional or empty",
  "music_cue": "M1"
}
```

Rules:
- Times must continue from previous batch if any; total durations in this batch ≈ {{batch_seconds}} seconds.
- Same cartoon guide for anchor scenes.
- **English only** for `vo_excerpt`, `on_screen_text`, `motion`, `sfx_note`.
- Return ONLY `{"scene_table": [ ... {{batch_count}} items ... ]}`.
