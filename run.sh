#!/usr/bin/env bash
# Textbook video run: .venv for LLM + MiniMax-H3 video; gsplat_env for Flux keyframes (and LTX if --video-backend ltx).
set -euo pipefail

cd /devwork/teja/EducationContentGeneration
source .venv/bin/activate

export HF_HOME=/workspace/teja/models/hub
export HF_HUB_CACHE=$HF_HOME

export PDF="/workspace/teja/ai_vidya/input/phaseII/telugu/pdfs/diksha/do_31310845228076236813575_7th_Class_Social_Studies_TM_PDF_Text_Book.pdf"
export BOOK_ID="do_31310845228076236813575"
export VIDEO_ID="v11_ch_11.1"
export RUN="output/textbooks/${BOOK_ID}/videos/${VIDEO_ID}"

# Flux / LTX stages need torch+diffusers (gsplat_env), not project .venv.
CONDA_SH="${CONDA_SH:-/devwork/MiniConda/miniconda3/etc/profile.d/conda.sh}"

run_gpu_pixels() {
  (
    # shellcheck disable=SC1090
    source "$CONDA_SH"
    conda activate gsplat_env
    export HF_HOME HF_HUB_CACHE
    unset TORCH_HOME
    exec python3 scripts/run_textbook_pixels.py "$@"
  )
}

# --- No LLM (GPU stays free later) ---
python3 scripts/run_textbook_pipeline.py \
  --pdf "$PDF" \
  --book-id "$BOOK_ID" \
  --heuristic-plan \
  --through cast \
  --output-root output

# --- LLM: ephemeral vLLM (gsplat only inside with_qwen_vllm.sh); pipeline stays on .venv ---
if [[ ! -f "$RUN/directing/directing_package.json" ]]; then
  ./scripts/with_qwen_vllm.sh bash -ec "
    python3 scripts/run_textbook_director.py \
      --book-id '$BOOK_ID' \
      --video-id '$VIDEO_ID' \
      --max-tokens 16384 \
      --output-root output
  "
else
  echo "Skip director — $RUN/directing/directing_package.json exists"
fi

if [[ ! -f "$RUN/background_audio/manifest.json" ]]; then
  if [[ ! -x .stable-audio-tflite/.venv/bin/python ]]; then
    bash scripts/setup_stable_audio.sh
  fi
  ./scripts/with_qwen_vllm.sh bash -ec "
    python3 scripts/stages/plan_background_music.py \
      --directing-package '$RUN/directing/directing_package.json' \
      --shot-decomposition '$RUN/shots/shot_decomposition.json' \
      --output-root '$RUN' \
      --and-generate
  "
else
  echo "Skip BGM — $RUN/background_audio/manifest.json exists"
fi

# --- GPU pixels (must use gsplat_env) ---
# export MINIMAX_API_KEY=...   # required for default MiniMax-H3 clip generation
run_gpu_pixels \
  --book-id "$BOOK_ID" \
  --video-id "$VIDEO_ID" \
  --output-root output \
  --gpu 1 \
  --skip-existing \
  --video-backend minimax

# --- Mux / QC (no vLLM, .venv is fine) ---
python3 scripts/run_pipeline.py \
  --output-root "$RUN" \
  --from-stage 5c \
  --to-stage 7 \
  --skip-reference-bank

ls -lh "$RUN/final_cut/"*.mp4
