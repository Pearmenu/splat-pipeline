#!/usr/bin/env bash
# One-command run on the pod. Sets every env we need (so no "colmap not found"
# or CPU-masking surprises) and runs the pipeline.
#
#   bash run.sh data/meu_video.mov
#   bash run.sh data/meu_video.mov --from-stage cleanup   # extra args pass through
set -euo pipefail

VIDEO="${1:?uso: bash run.sh data/<video> [--from-stage X]}"
shift || true

# colmap/glomap (micromamba prefix) + gsplat examples
export PATH="$PATH:/opt/splattools/bin"
export GSPLAT_DIR="${GSPLAT_DIR:-/opt/gsplat}"

# CUDA/cuDNN libs so onnxruntime-gpu (rembg masking) finds the CUDA provider
NVLIB=$(python - <<'PY' 2>/dev/null || true
import os, glob, nvidia
print(":".join(glob.glob(os.path.join(os.path.dirname(nvidia.__file__), "*", "lib"))))
PY
)
TORCHLIB=$(python -c "import os,torch;print(os.path.join(os.path.dirname(torch.__file__),'lib'))" 2>/dev/null || echo "")
export LD_LIBRARY_PATH="${NVLIB}:${TORCHLIB}:${LD_LIBRARY_PATH:-}"

echo "PATH ok · GSPLAT_DIR=$GSPLAT_DIR"
command -v colmap >/dev/null && echo "colmap: $(command -v colmap)" || echo "WARN: colmap não encontrado"
command -v glomap >/dev/null && echo "glomap: $(command -v glomap)" || echo "WARN: glomap não encontrado"
echo

python pipeline.py --video "$VIDEO" --workdir data/run "$@"
