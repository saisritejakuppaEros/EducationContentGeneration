#!/usr/bin/env bash
# Generate LTX 2.3 image-to-video clips with native audio.
#
# Models are cached under HF_HOME (not TORCH_HOME).
#
# One-time setup (gsplat_env):
#   pip install 'diffusers>=0.39.0'
#
# First run downloads weights into /workspace/teja/models/hub:
#   bash scripts/run_all_ltx_videos.sh --scene S0
#
# Resume / skip completed shots:
#   bash scripts/run_all_ltx_videos.sh --skip-existing

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
export HF_HUB_CACHE="$HF_HOME"
unset TORCH_HOME

SCENES=()
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scene)
      SCENES+=("$2")
      shift 2
      ;;
    *)
      EXTRA+=("$1")
      shift
      ;;
  esac
done

SCENE_ARGS=()
if ((${#SCENES[@]})); then
  for s in "${SCENES[@]}"; do
    SCENE_ARGS+=(--scene "$s")
  done
fi

echo "HF_HOME: $HF_HOME"
echo "Extra:   ${EXTRA[*]:-(none)}"
echo "Scenes:  ${SCENES[*]:-all renderable shots}"
echo

python scripts/legacy/generate_ltx_videos.py \
  "${SCENE_ARGS[@]}" \
  --skip-existing \
  ${EXTRA+"${EXTRA[@]}"}

echo
echo "Done. Videos and manifest:"
echo "  output/ltx_videos/manifest.json"
echo "  output/ltx_videos/S*/S*_shot*.mp4"
