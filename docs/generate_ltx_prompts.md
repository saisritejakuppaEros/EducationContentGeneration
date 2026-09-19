# generate_ltx_prompts

Turns Flux still prompts into structured LTX 2.3 audio-video prompts for image-to-video generation.

## Purpose

Stage 6 of the pipeline: for each shot in `flux_prompts.json`, produce tagged prompts that drive LTX 2.3 native audio+video from the matching Flux PNG init frame.

## Inputs

- `output/flux_prompts/flux_prompts.json` — enhanced Flux prompts + wan_motion + dialogue (default)
- `prompts/ltx_prompt_enhancement.md` — prompt template
- `samples/ltx_prompts.json` — reference quality/schema
- **Qwen (default):** vLLM at `http://localhost:8000/v1` serving `Qwen/Qwen3.5-27B`
- **Gemma (optional):** `gemma4_model/` local weights via `--backend gemma`

## Outputs

All artifacts go under `output/ltx_prompts/`:

- `ltx_prompts.json` — scenes with LTX prompts per shot

## Prompt modes

| `ltx_mode` | When | LoRA | Tags |
|---|---|---|---|
| `talking_head` | Human face visible + single-speaker dialogue | `use_talking_head_lora: true` | `[VISUAL]` `[SPEECH]` `[SOUNDS]` |
| `cinematic` | Establishing, insert, title, reaction without speech | `false` | `[VISUAL]` `[SOUNDS]` |
| `skip` | `MATH INSERT` (Manim handles these) | `false` | — |

## JSON shape

Each shot keeps original flux fields plus:

- `ltx_mode` — `talking_head`, `cinematic`, or `skip`
- `use_talking_head_lora` — whether to load the talking-head AV LoRA at inference
- `speaker` — `M`, `F`, `Y`, or null
- `init_image` — path to Flux PNG (e.g. `output/flux_images/S0/S0_shot01.png`)
- `motion_summary` — one-line motion note from `wan_motion`
- `ltx_prompt` — full tagged string ready for LTX inference
- `ltx_prompt_structured` — `{ visual, speech, sounds }`
- `negative_prompt` — default AV negative prompt (suppresses silent output, music, bad lipsync)

## Usage

With vLLM serving Qwen (see readme.md):

```bash
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=openai/Qwen/Qwen3.5-27B

python scripts/legacy/generate_ltx_prompts.py --scene S0
```

Default backend is **qwen** (vLLM). Use local Gemma instead:

```bash
python scripts/legacy/generate_ltx_prompts.py --backend gemma
```

Process specific scenes only:

```bash
python scripts/legacy/generate_ltx_prompts.py --scene S0 --scene S1
```

Optional flags: `--input`, `--reference`, `--prompt`, `--backend`, `--qwen-model`, `--api-base`, `--model-path`, `--flux-images-dir`, `--output-file`, `--max-new-tokens`, `--temperature`, `--disable-thinking`.
