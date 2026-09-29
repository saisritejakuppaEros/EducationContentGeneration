# v2 — Agentic editing stack

v2 is the workspace for **agentic AI software** that drives two local editors:

| Editor | Repo | Role |
|--------|------|------|
| **Maestro** | [Blizaine/Maestro](https://github.com/Blizaine/Maestro) | AI creative studio + director + timeline editor (generation → edit) |
| **Concat** | [jub0t/Concat](https://github.com/jub0t/Concat) | Native Rust NLE with JSON-RPC / gRPC API for scripted edits |

v1 (`scripts/v1/`) remains the textbook → film **generation** pipeline. v2 adds the **editing** layer agents will orchestrate.

## Layout

```
scripts/v2/
  README.md
  setup_maestro.sh      # Python env + UI build (NVIDIA GPU required)
  setup_concat.sh       # Rust toolchain + cargo build
  start_maestro.sh      # Launch Maestro backend
  start_concat.sh       # Launch Concat editor (+ API on localhost)

  Maestro/              # git clone of Blizaine/Maestro
  Concat/               # git clone of jub0t/Concat
```

## Prerequisites

**Maestro**

- NVIDIA GPU (6 GB+ VRAM; this machine: Blackwell sm_120 → `app/env-rtx50`, Python 3.11, CUDA 13)
- Driver 580+ (CUDA 13)
- `uv`, `npm`, `git`, `ffmpeg`

**Concat**

- Rust 1.93+ (`rust-toolchain.toml` in `Concat/src/`)
- FFmpeg 7+ dev libraries
- `cmake`, C++ compiler

## Quick setup

```bash
cd /devwork/teja/EducationContentGeneration/scripts/v2

# Maestro (large download — torch, models on first run)
./setup_maestro.sh

# Concat (first run installs Rust if missing)
./setup_concat.sh
```

## Run

```bash
./start_maestro.sh    # http://127.0.0.1:<port>  (see terminal output)
./start_concat.sh     # editor window + JSON-RPC API on 127.0.0.1:7420
```

### Concat API (for agents)

With the window open, Concat serves the API documented in `Concat/docs/`:

- JSON-RPC: `127.0.0.1:7420` — see `Concat/docs/transports/json-rpc.md`
- gRPC: `127.0.0.1:7421` — see `Concat/docs/transports/grpc.md`

Token is printed at startup (or in Settings → Developer).

## Update upstream

```bash
cd Maestro && git pull
cd ../Concat && git pull
```

Re-run the matching `setup_*.sh` after pulling if dependencies changed.

## Agent integration (planned)

- **Maestro agent** — director / studio / editor workflows via Maestro's FastAPI backend
- **Concat agent** — programmatic timeline edits via JSON-RPC or gRPC

See root `plan.md` for the full v2 architecture.
