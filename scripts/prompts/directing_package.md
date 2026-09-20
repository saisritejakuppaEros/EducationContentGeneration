# System

(Full director rules are in the system message loaded from scripts/knowledge/director_skill.md.)

# User

You are executing the NCERT Explainer Director workflow. Produce **only valid JSON** matching the schema below — no markdown wrapper, no commentary.

**Chapter source text:**

```
{{chapter_text}}
```

**Constraints for this run:**
- Target runtime: {{runtime_seconds}} seconds (~{{runtime_minutes}} minutes).
- **Scene budget:** exactly **{{scene_count_min}}–{{scene_count_max}}** rows in `scene_table` (average ~{{scene_seconds_avg}} s/scene). Do not exceed {{scene_count_max}} — output must fit in one JSON object.
- **Language: English only** for all narration, titles, on-screen text, and image prompts (translate syllabus; no Assamese/other scripts in output fields).
- Cast: use the **standard cartoon guide** (`assets/cartoon/image.png`) for all characters (M, F, Y) — same design every scene.
- Output must be **timeline-first**: every scene row has `time_start` / `duration_seconds` that sum to the target runtime.
- `audio_cue_sheet` is for the **background-music agent only** (instrumental beds). Do not embed music generation in VO.
- Keep `vo_excerpt` ≤ 8 words; `script` VO blocks can be fuller but concise.
- **`image_prompts`:** at most **{{image_prompt_max}}** entries (dedupe repeated visuals).

Required JSON schema:

```json
{
  "title": "string",
  "chapter": "string",
  "class_level": "string",
  "subject": "string",
  "runtime_target_seconds": 540,
  "chapter_brief": {
    "core_question": "string",
    "key_terms": ["max 6"],
    "engine": "cascade | tug-of-war | myth-flip | puzzle | diagram-build | chronology | taxonomy",
    "misconceptions": ["string"],
    "syllabus_boundary": "string",
    "audio_role": "bed | punctuation | voice-only",
    "tone_dial": 0
  },
  "style_guide": "paste STYLE GUIDE block as a single string",
  "beat_sheet": [
    {
      "beat_number": 1,
      "time_start": "0:00",
      "time_end": "0:30",
      "label": "HOOK",
      "turn_ids": ["T1"],
      "music_intensity": "2-3"
    }
  ],
  "script": [
    {
      "time_start": "0:00",
      "time_end": "0:30",
      "beat_label": "HOOK",
      "vo": "full narration with [pause] markup",
      "on_screen": "short labels only"
    }
  ],
  "scene_table": [
    {
      "scene_id": "S01",
      "time_start": "0:00",
      "duration_seconds": 5.0,
      "vo_excerpt": "first few words",
      "visual_mode": "illustrated | diagram | anchor | map | text_card",
      "anchor_present": false,
      "on_screen_text": "3-5 words",
      "motion": "slow zoom-in",
      "sfx_note": "optional, diegetic only",
      "music_cue": "M1"
    }
  ],
  "image_prompts": [
    {
      "scene_id": "S01",
      "prompt": "full image gen prompt per director template",
      "duration_seconds": 5.0
    }
  ],
  "audio_cue_sheet": [
    {
      "cue_id": "M1",
      "time_start": "0:00",
      "time_end": "0:30",
      "mood": "string",
      "instruments": "string",
      "intensity": "2-3",
      "mix_notes": "duck under VO",
      "stable_audio_prompt": "one paragraph instrumental prompt, no vocals"
    }
  ],
  "turn_ledger": [{"turn_id": "T1", "timestamp": "0:20", "change": "string"}],
  "plant_payoff": [{"plant": "string", "payoff_beat": "APPLICATION"}],
  "titles": ["5 options"],
  "recommended_title": "string",
  "qa_notes": ["short PASS/FAIL bullets you fixed"]
}
```

Rules:
- Respect the scene budget above (textbook / 8-min units typically 30–45 scenes, not 100+).
- Curriculum accuracy: flag non-NCERT claims in `qa_notes` as `[EXTERNAL - verify]`.
- `image_prompts`: dedupe repeated visuals; stay within {{image_prompt_max}} entries.
