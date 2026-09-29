#!/usr/bin/env bash
# Manual Maestro install (Pinokio-free). Mirrors install.js + torch.js for Linux sm_120.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MAESTRO="$ROOT/Maestro"
APP="$MAESTRO/app"
ENV_DIR="$APP/env-rtx50"
PYTHON="3.11"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "Maestro requires an NVIDIA GPU." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

cd "$MAESTRO"

echo "==> Creating Python $PYTHON venv at $ENV_DIR"
uv venv "$ENV_DIR" --python "$PYTHON"
# shellcheck disable=SC1091
source "$ENV_DIR/bin/activate"

echo "==> Installing Python dependencies"
cd "$APP"
uv pip install -r requirements.txt --index-strategy unsafe-best-match
uv pip install hf-xet pip

echo "==> Installing PyTorch 2.10 / CUDA 13 runtime (Blackwell / Sol path)"
uv pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 \
  --index-url https://download.pytorch.org/whl/cu130 --force-reinstall --no-deps
uv pip install xformers==0.0.35 \
  --index-url https://download.pytorch.org/whl/cu130 --force-reinstall --no-deps
uv pip install 'triton>=3.6,<3.7' --force-reinstall
uv pip install \
  https://github.com/deepbeepmeep/kernels/releases/download/Light2xv/lightx2v_kernel-0.0.2+torch2.10.0-cp311-abi3-linux_x86_64.whl \
  --force-reinstall --no-deps
uv pip install \
  https://github.com/nunchaku-ai/nunchaku/releases/download/v1.2.1/nunchaku-1.2.1+cu13.0torch2.10-cp311-cp311-linux_x86_64.whl \
  --force-reinstall --no-deps

export TORCH_CUDA_ARCH_LIST="12.0"
export MAX_JOBS="${MAX_JOBS:-4}"
python scripts/install_optional_cuda_acceleration.py || true
python scripts/install_optional_cuda_acceleration.py --flash-only || true
python scripts/install_gguf_kernels.py || true

touch "$ENV_DIR/.maestro_torch_rtx50_v2.installed"
touch "$ENV_DIR/.maestro_flash_2_8_3_v1.installed"

if [[ ! -f postprocessing/seedvc/__init__.py ]]; then
  echo "==> Cloning seed-vc component"
  git clone --depth 1 --branch v1.0.0 \
    https://github.com/Blizaine/maestro-seedvc postprocessing/seedvc
fi

if [[ -f "$MAESTRO/ui/package.json" ]]; then
  echo "==> Building Maestro UI"
  cd "$MAESTRO/ui"
  npm install
  npm run build
fi

echo ""
echo "Maestro setup complete."
echo "Start with: $ROOT/start_maestro.sh"
