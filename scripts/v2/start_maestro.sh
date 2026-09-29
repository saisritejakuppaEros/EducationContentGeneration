#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/Maestro/app"

for env in env-rtx50 env-sol env; do
  if [[ -f "$APP/$env/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$APP/$env/bin/activate"
    cd "$APP"
    exec python launch.py "$@"
  fi
done

echo "Maestro not installed. Run: $ROOT/setup_maestro.sh" >&2
exit 1
