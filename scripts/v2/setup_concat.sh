#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONCAT="$ROOT/Concat/src"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg is required. Install FFmpeg 7+ and dev headers." >&2
  exit 1
fi

if ! pkg-config --exists openssl 2>/dev/null; then
  echo "OpenSSL dev headers required (Ubuntu: sudo apt install libssl-dev pkg-config cmake libclang-dev)" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "==> Installing Rust via rustup"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.93
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
fi

echo "==> Building Concat (release)"
cd "$CONCAT"
cargo build -p concat --release

echo ""
echo "Concat setup complete."
echo "Binary: $CONCAT/target/release/concat"
echo "Start with: $ROOT/start_concat.sh"
