#!/usr/bin/env bash
# Set up the pipeline on a bare RunPod PyTorch pod (no Docker needed).
# Use this to validate Phase 1 on a real dish video before deploying serverless.
#
#   bash scripts/setup_pod.sh
#   GSPLAT_DIR=/opt/gsplat python pipeline.py --video data/prato.mp4 --workdir data/run
set -euo pipefail

apt-get update
apt-get install -y --no-install-recommends \
  git wget ffmpeg libgl1 libglib2.0-0 build-essential ninja-build

# COLMAP + GLOMAP (CUDA builds). Pin the CUDA variant explicitly if the default
# resolves to a CPU-only build: conda install -c conda-forge "colmap=*=*cuda*" glomap
conda install -y -c conda-forge colmap glomap

pip install -r requirements.txt
pip install gsplat

git clone --depth 1 https://github.com/nerfstudio-project/gsplat /opt/gsplat || true
pip install -r /opt/gsplat/examples/requirements.txt || true

echo
echo "Setup done. GSPLAT_DIR=/opt/gsplat"
echo "Test:  GSPLAT_DIR=/opt/gsplat python pipeline.py --video <video> --workdir <out>"
