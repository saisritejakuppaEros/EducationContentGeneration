#!/usr/bin/env bash
#
# One-time setup for Stable Audio 3 (CPU / LiteRT) using weights from
# stabilityai/stable-audio-3-optimized on Hugging Face.
#
# Usage:
#   ./scripts/setup_stable_audio.sh
#   ./scripts/setup_stable_audio.sh --download sm-music,sm-sfx
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TFLITE_DIR="$ROOT/.stable-audio-tflite"
SRC_DIR="$ROOT/.stable-audio-src"
DOWNLOAD_BUNDLES="${1:-sm-music}"

export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"

if [[ "${1:-}" == "--download" ]]; then
  DOWNLOAD_BUNDLES="${2:-sm-music}"
fi

step() { printf '\n→ %s\n' "$1"; }

if [[ ! -f "$TFLITE_DIR/install.sh" ]]; then
  step "Fetching Stable Audio 3 TFLite runtime (sparse clone)"
  rm -rf "$SRC_DIR"
  git clone --depth 1 --filter=blob:none --sparse https://github.com/Stability-AI/stable-audio-3.git "$SRC_DIR"
  (
    cd "$SRC_DIR"
    git sparse-checkout set optimized/tflite
  )
  rm -rf "$TFLITE_DIR"
  mv "$SRC_DIR/optimized/tflite" "$TFLITE_DIR"
  rm -rf "$SRC_DIR"
fi

step "Installing LiteRT deps + pre-downloading bundles: $DOWNLOAD_BUNDLES"
(
  cd "$TFLITE_DIR"
  ./install.sh -y --download "$DOWNLOAD_BUNDLES"
)

step "Done. TFLite root: $TFLITE_DIR"
echo "Generate a sample:"
echo "  python3 scripts/stages/generate_background_audio.py --sample"
