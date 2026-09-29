#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="$ROOT/Concat/src/target/release/concat"

if [[ ! -x "$BIN" ]]; then
  BIN="$ROOT/Concat/src/target/debug/concat"
fi

if [[ ! -x "$BIN" ]]; then
  echo "Concat not built. Run: $ROOT/setup_concat.sh" >&2
  exit 1
fi

exec "$BIN" "$@"
