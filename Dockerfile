# PeAR Splat Pipeline — GPU worker image.
# Build/run on an NVIDIA host (RunPod RTX 4090 / L40S recommended).
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    GSPLAT_DIR=/opt/gsplat

RUN apt-get update && apt-get install -y --no-install-recommends \
        git wget ffmpeg libgl1 libglib2.0-0 build-essential ninja-build \
    && rm -rf /var/lib/apt/lists/*

# COLMAP + GLOMAP (CUDA-enabled builds from conda-forge).
# NOTE: if the CUDA variant isn't selected automatically, pin it explicitly, e.g.
#   conda install -c conda-forge "colmap=*=*cuda*" glomap
RUN conda install -y -c conda-forge colmap glomap && conda clean -afy

# Python deps for the pipeline stages.
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# gsplat (CUDA build) + its example trainer (simple_trainer.py provides the MCMC strategy).
RUN pip install gsplat \
    && GSV=$(python -c "import gsplat; print(gsplat.__version__)") \
    && (git clone --depth 1 --branch "v$GSV" https://github.com/nerfstudio-project/gsplat ${GSPLAT_DIR} \
        || git clone --depth 1 https://github.com/nerfstudio-project/gsplat ${GSPLAT_DIR}) \
    && pip install --no-build-isolation -r ${GSPLAT_DIR}/examples/requirements.txt || true

WORKDIR /workspace
COPY . /workspace

ENTRYPOINT ["python", "pipeline.py"]
