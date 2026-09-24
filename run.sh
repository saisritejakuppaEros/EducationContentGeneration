#!/usr/bin/env bash
# One-command Telugu textbook video pipeline (ingest → LLM → pixels → final MP4).
#
#   cd /devwork/teja/EducationContentGeneration && ./run.sh
#   FRESH=1 ./run.sh          # wipe this VIDEO_ID and regenerate everything
#
# No manual vLLM, GPU index, or QWEN_MODEL setup — run.sh picks GPUs and starts/stops vLLM.
#
set -euo pipefail

ROOT="/devwork/teja/EducationContentGeneration"
cd "$ROOT"

if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  echo "[run.sh] Missing .venv — create the project venv first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- Target (Telugu 7th Social Studies) ---
export PDF="${PDF:-/workspace/teja/ai_vidya/input/phaseII/telugu/pdfs/diksha/do_31310845228076236813575_7th_Class_Social_Studies_TM_PDF_Text_Book.pdf}"
export BOOK_ID="${BOOK_ID:-do_31310845228076236813575}"
export VIDEO_ID="${VIDEO_ID:-v11_ch_11.1}"
export RUN="output/textbooks/${BOOK_ID}/videos/${VIDEO_ID}"
BOOK_ROOT="output/textbooks/${BOOK_ID}"

export FRESH="${FRESH:-0}"
export STEP="${STEP:-all}"
export VIDEO_BACKEND="${VIDEO_BACKEND:-ltx}"

export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"

export OPENAI_API_BASE="${OPENAI_API_BASE:-http://localhost:8007/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-local}"
# Always use pipeline text model (ignore shell QWEN_MODEL / Qwen3-VL exports).
unset QWEN_MODEL 2>/dev/null || true
export QWEN_MODEL="${PIPELINE_QWEN_MODEL:-Qwen/Qwen3.5-27B}"

CONDA_SH="${CONDA_SH:-/devwork/MiniConda/miniconda3/etc/profile.d/conda.sh}"
GPU_PICK="$ROOT/scripts/gpu_autopick.sh"

log() { echo "[run.sh] $*"; }

assign_gpu() {
  local var_name="$1"
  if [[ -n "${!var_name:-}" && "${AUTO_GPU:-1}" == "0" ]]; then
    return 0
  fi
  # shellcheck disable=SC1090
  eval "$(bash "$GPU_PICK" export "$var_name")"
}

preflight() {
  if [[ ! -f "$PDF" ]]; then
    echo "[run.sh] PDF not found: $PDF" >&2
    exit 1
  fi
  if [[ ! -f "$CONDA_SH" ]]; then
    echo "[run.sh] Conda not found at $CONDA_SH (needed for vLLM / Flux / LTX)." >&2
    exit 1
  fi
  mkdir -p output/pipeline
  log "Qwen model: $QWEN_MODEL | video backend: $VIDEO_BACKEND"
  bash "$GPU_PICK" log || true
}

wipe_fresh() {
  case "$FRESH" in
    0 | "" | false | no) return 0 ;;
    book)
      log "FRESH=book — removing ${BOOK_ROOT}/"
      rm -rf "${BOOK_ROOT}"
      ;;
    1 | yes | true | video)
      log "FRESH=1 — removing ${RUN}/"
      rm -rf "${RUN}"
      ;;
    pixels)
      log "FRESH=pixels — removing pixel + final artifacts under ${RUN}/"
      rm -rf "${RUN}/shots/keyframes" \
        "${RUN}/cinematic_videos" \
        "${RUN}/html_inserts" \
        "${RUN}/manim_videos" \
        "${RUN}/audio" \
        "${RUN}/final_cut" \
        "${RUN}/pixels_manifest.json"
      ;;
    *)
      echo "Unknown FRESH=$FRESH (use 0, 1, book, or pixels)" >&2
      exit 1
      ;;
  esac
}

ensure_series_profile() {
  local profile="${BOOK_ROOT}/series_profile/series_profile.json"
  local bible="${BOOK_ROOT}/series_bible/series_bible.json"
  if [[ -f "$profile" ]]; then
    return 0
  fi
  if [[ -f "$bible" ]]; then
    log "Linking series_bible → series_profile for pixel stages"
    mkdir -p "${BOOK_ROOT}/series_profile"
    cp -f "$bible" "$profile"
    if [[ -d "${BOOK_ROOT}/series_bible/reference_photos" ]]; then
      rm -rf "${BOOK_ROOT}/series_profile/reference_photos"
      cp -a "${BOOK_ROOT}/series_bible/reference_photos" "${BOOK_ROOT}/series_profile/reference_photos"
    fi
    return 0
  fi
  return 1
}

run_gpu_pixels() {
  ensure_series_profile || {
    echo "[run.sh] Missing series profile — run full pipeline first." >&2
    exit 1
  }
  assign_gpu GPU
  log "Flux/LTX on GPU ${GPU}"
  (
    # shellcheck disable=SC1090
    source "$CONDA_SH"
    conda activate gsplat_env
    export HF_HOME HF_HUB_CACHE
    unset TORCH_HOME
    exec python3 scripts/run_textbook_pixels.py "$@"
  )
}

check_minimax_env() {
  if [[ "$VIDEO_BACKEND" != "minimax_h3" ]]; then
    return 0
  fi
  if [[ -z "${MINIMAX_H3_I2V_WORKFLOW:-}" || -z "${MINIMAX_H3_I2V_PATCH:-}" || -z "${MINIMAX_H3_OUTPUT_NODE:-}" ]]; then
    log "VIDEO_BACKEND=minimax_h3 but ComfyUI is not configured — falling back to ltx"
    export VIDEO_BACKEND=ltx
  fi
}

step_ingest() {
  local force_flag=()
  if [[ "$FRESH" == "book" ]]; then
    force_flag=(--force)
  fi
  log "Ingest: extract PDF → plan → cast"
  python3 scripts/run_textbook_pipeline.py \
    --pdf "$PDF" \
    --book-id "$BOOK_ID" \
    --heuristic-plan \
    --through cast \
    --output-root output \
    "${force_flag[@]}"
  ensure_series_profile || true
}

step_reference_bank() {
  local profile="${BOOK_ROOT}/series_profile/series_profile.json"
  [[ -f "$profile" ]] || ensure_series_profile
  REF_BANK="${BOOK_ROOT}/series_profile/reference_photos/manifest.json"
  if [[ -f "$REF_BANK" && "$FRESH" != "1" && "$FRESH" != "book" && "$FRESH" != "pixels" ]]; then
    log "Skip reference bank — already built"
    return 0
  fi
  assign_gpu GPU
  log "Reference bank (cast continuity) on GPU ${GPU}"
  (
    # shellcheck disable=SC1090
    source "$CONDA_SH"
    conda activate gsplat_env
    export HF_HOME HF_HUB_CACHE
    export CUDA_VISIBLE_DEVICES="$GPU"
    python3 scripts/stages/build_reference_bank.py \
      --series-profile "$profile" \
      --output-dir "${BOOK_ROOT}/series_profile/reference_photos" \
      --output-root output \
      --skip-existing \
      --tag close_up_neutral \
      --tag wide_full_body_neutral_pose \
      --tag three_quarter_left \
      --tag three_quarter_right
  )
}

step_llm() {
  local need_director=0 need_bgm=0
  local skip=(--skip-existing)

  if [[ ! -f "$RUN/directing/directing_package.json" || "$FRESH" == "1" || "$FRESH" == "book" ]]; then
    need_director=1
    skip=()
  fi
  if [[ ! -f "$RUN/background_audio/manifest.json" || "$FRESH" == "1" || "$FRESH" == "book" ]]; then
    need_bgm=1
  fi

  if [[ "$need_director" == "0" ]]; then
    log "Skip director — already present"
  fi
  if [[ "$need_bgm" == "0" ]]; then
    log "Skip BGM — already present"
  fi
  if [[ "$need_director" -eq 0 && "$need_bgm" -eq 0 ]]; then
    return 0
  fi

  if [[ "$need_bgm" == "1" && ! -x .stable-audio-tflite/.venv/bin/python ]]; then
    log "Setting up Stable Audio (first time)"
    bash scripts/setup_stable_audio.sh
  fi

  assign_gpu VLLM_GPU_ID
  log "LLM stages on GPU ${VLLM_GPU_ID} (single vLLM session for director + BGM)"

  local inner=""
  if [[ "$need_director" == "1" ]]; then
    inner="python3 scripts/run_textbook_director.py \
      --book-id '$BOOK_ID' \
      --video-id '$VIDEO_ID' \
      --max-tokens 16384 \
      --output-root output"
    if [[ ${#skip[@]} -gt 0 ]]; then
      inner+=" ${skip[*]}"
    fi
  fi
  if [[ "$need_bgm" == "1" ]]; then
    [[ -n "$inner" ]] && inner+=" && "
    inner+="python3 scripts/stages/plan_background_music.py \
      --directing-package '$RUN/directing/directing_package.json' \
      --shot-decomposition '$RUN/shots/shot_decomposition.json' \
      --output-root '$RUN' \
      --and-generate"
  fi

  ./scripts/with_qwen_vllm.sh bash -ec "$inner"

  # Release VRAM before Flux/LTX.
  sleep 5
  bash "$GPU_PICK" log || true
}

step_pixels() {
  check_minimax_env
  assign_gpu GPU
  local pixel_args=(
    --book-id "$BOOK_ID"
    --video-id "$VIDEO_ID"
    --output-root output
    --gpu "$GPU"
    --skip-existing
    --video-backend "$VIDEO_BACKEND"
  )
  if [[ "$FRESH" == "pixels" || "$FRESH" == "1" ]]; then
    pixel_args=( "${pixel_args[@]/--skip-existing/}" )
  fi
  log "Pixels: Flux keyframes → ${VIDEO_BACKEND}"
  run_gpu_pixels "${pixel_args[@]}"
}

step_finish() {
  log "Narration TTS (stage 6)"
  python3 scripts/run_pipeline.py \
    --output-root "$RUN" \
    --from-stage 6 \
    --to-stage 6 \
    --skip-reference-bank \
    --force

  log "QC + final mux (5c → 7)"
  python3 scripts/run_pipeline.py \
    --output-root "$RUN" \
    --from-stage 5c \
    --to-stage 7 \
    --skip-reference-bank \
    --force

  if compgen -G "${RUN}/final_cut/"*.mp4 >/dev/null; then
    ls -lh "${RUN}/final_cut/"*.mp4
  else
    echo "[run.sh] No final_cut MP4 — check cinematic_videos/ logs." >&2
    exit 1
  fi
}

# --- Main ---
preflight
log "BOOK_ID=$BOOK_ID VIDEO_ID=$VIDEO_ID STEP=$STEP FRESH=$FRESH"
log "Output: $RUN"

wipe_fresh

case "$STEP" in
  all)
    step_ingest
    step_llm
    step_reference_bank
    step_pixels
    step_finish
    ;;
  ingest)
    step_ingest
    step_reference_bank
    ;;
  llm)
    step_llm
    ;;
  pixels)
    step_reference_bank
    step_pixels
    step_finish
    ;;
  finish)
    step_finish
    ;;
  *)
    echo "Unknown STEP=$STEP" >&2
    exit 1
    ;;
esac

log "Done."
