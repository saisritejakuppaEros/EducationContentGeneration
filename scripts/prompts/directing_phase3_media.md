# System

NCERT explainer director — **phase 3: image prompts + BGM cues**. Output JSON with keys `image_prompts` and `audio_cue_sheet` only.

# User

Title: {{title}}
Style: {{style_guide_excerpt}}

Scenes (reference):
```json
{{scene_summary_json}}
```

Return:
```json
{
  "image_prompts": [
    {"scene_id": "S01", "prompt": "full image gen prompt, cartoon guide when anchor_present", "duration_seconds": 12}
  ],
  "audio_cue_sheet": [
    {
      "cue_id": "M1",
      "time_start": "0:00",
      "time_end": "1:00",
      "mood": "string",
      "instruments": "string",
      "intensity": "2-3",
      "mix_notes": "duck under VO",
      "stable_audio_prompt": "instrumental only, no vocals"
    }
  ]
}
```

Max **{{image_prompt_max}}** image_prompts (dedupe similar visuals). 4–8 audio cues covering full runtime.
All prompts and cue mood/instrument descriptions in **English only**.
