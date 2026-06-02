#!/usr/bin/env bash
# Set up the pipeline on a bare RunPod PyTorch pod (no Docker needed).
# Tested target: "Runpod Pytorch 2.4.0" template (cuda12.4.1-devel, py3.11).
# Use this to validate Phase 1 on a real dish video before deploying serverless.
#
#   bash scripts/setup_pod.sh
#   python pipeline.py --video data/prato.mp4 --workdir data/run
set -euo pipefail

PREFIX=/opt/splattools

echo "[1/4] system packages (ffmpeg, OpenGL, build tools)…"
apt-get update
apt-get install -y --no-install-recommends \
  git wget curl ca-certificates ffmpeg libgl1 libglib2.0-0 build-essential ninja-build

echo "[2/4] COLMAP + GLOMAP via micromamba (RunPod pods have no conda)…"
if ! command -v micromamba >/dev/null 2>&1; then
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xj -C /usr/local bin/micromamba
fi
# Isolated prefix so it never shadows the pod's Python/torch. We append (not
# prepend) its bin to PATH, so only `colmap`/`glomap` resolve from here.
# Pin COLMAP to the 3.x line: the conda-forge 4.0.x build drags a broken
# faiss->MKL runtime chain (libmkl_intel_lp64.so.2 missing). 3.11 is the stable,
# self-contained build everyone uses for 3DGS.
micromamba create -y -p "$PREFIX" -c conda-forge "colmap<4" glomap
export PATH="$PATH:$PREFIX/bin"
grep -q "$PREFIX/bin" ~/.bashrc 2>/dev/null || echo "export PATH=\$PATH:$PREFIX/bin" >> ~/.bashrc

echo "[3/4] Python deps (uses the pod's preinstalled torch/CUDA)…"
pip install -r requirements.txt
pip install gsplat

# Make rembg masking run on the GPU (CPU is ~40x slower: 67 min vs <1 min).
# The CPU onnxruntime build shadows the CUDA provider, so keep only the GPU one,
# and expose torch's bundled CUDA/cuDNN libs so ORT can load the CUDA provider.
echo "    configurando masking na GPU (onnxruntime-gpu)…"
pip uninstall -y onnxruntime >/dev/null 2>&1 || true
python -c "import onnxruntime" 2>/dev/null || pip install onnxruntime-gpu
NVLIB=$(python - <<'PY' 2>/dev/null || true
import os, glob, nvidia
print(":".join(glob.glob(os.path.join(os.path.dirname(nvidia.__file__), "*", "lib"))))
PY
)
TORCHLIB=$(python -c "import os,torch;print(os.path.join(os.path.dirname(torch.__file__),'lib'))" 2>/dev/null || echo "")
LDADD="${NVLIB}:${TORCHLIB}"
grep -q "# splat-cuda-libs" ~/.bashrc 2>/dev/null \
  || echo "export LD_LIBRARY_PATH=\"${LDADD}:\${LD_LIBRARY_PATH:-}\" # splat-cuda-libs" >> ~/.bashrc
export LD_LIBRARY_PATH="${LDADD}:${LD_LIBRARY_PATH:-}"

echo "[4/4] gsplat example trainer (matching version, simple_trainer.py)…"
# Clone the examples at the SAME tag as the installed gsplat, so simple_trainer.py
# matches the library API. Fall back to main if the tag isn't found.
GSV=$(python -c "import gsplat; print(gsplat.__version__)" 2>/dev/null || echo "")
rm -rf /opt/gsplat
git clone --depth 1 --branch "v$GSV" https://github.com/nerfstudio-project/gsplat /opt/gsplat \
  || git clone --depth 1 https://github.com/nerfstudio-project/gsplat /opt/gsplat
# --no-build-isolation so packages whose setup.py imports torch at build time
# (ppisp, fused-ssim, fused-bilagrid) can see the already-installed torch instead
# of failing in an isolated build env.
pip install --no-build-isolation -r /opt/gsplat/examples/requirements.txt || true
grep -q "GSPLAT_DIR" ~/.bashrc 2>/dev/null || echo "export GSPLAT_DIR=/opt/gsplat" >> ~/.bashrc
export GSPLAT_DIR=/opt/gsplat

echo
command -v colmap >/dev/null && echo "colmap OK" || echo "WARN: colmap não encontrado no PATH"
command -v glomap >/dev/null && echo "glomap OK" || echo "WARN: glomap não encontrado no PATH"
echo
echo "Setup done. Agora rode:"
echo "  python pipeline.py --video data/prato.mp4 --workdir data/run"
