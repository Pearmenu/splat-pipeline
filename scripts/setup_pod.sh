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
micromamba create -y -p "$PREFIX" -c conda-forge colmap glomap
export PATH="$PATH:$PREFIX/bin"
grep -q "$PREFIX/bin" ~/.bashrc 2>/dev/null || echo "export PATH=\$PATH:$PREFIX/bin" >> ~/.bashrc

echo "[3/4] Python deps (uses the pod's preinstalled torch/CUDA)…"
pip install -r requirements.txt
pip install gsplat

echo "[4/4] gsplat example trainer (simple_trainer.py)…"
git clone --depth 1 https://github.com/nerfstudio-project/gsplat /opt/gsplat || true
pip install -r /opt/gsplat/examples/requirements.txt || true
grep -q "GSPLAT_DIR" ~/.bashrc 2>/dev/null || echo "export GSPLAT_DIR=/opt/gsplat" >> ~/.bashrc
export GSPLAT_DIR=/opt/gsplat

echo
colmap -h >/dev/null 2>&1 && echo "colmap OK" || echo "WARN: colmap não respondeu"
glomap -h >/dev/null 2>&1 && echo "glomap OK" || echo "WARN: glomap não respondeu"
echo
echo "Setup done. Agora rode:"
echo "  python pipeline.py --video data/prato.mp4 --workdir data/run"
