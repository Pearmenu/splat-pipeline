"""Stage 3 — camera poses via Structure from Motion.

COLMAP extracts + matches features (masked, so background is ignored), then
GLOMAP solves the global reconstruction (much faster than COLMAP's incremental
mapper). Output is a sparse model in colmap/sparse/0 that gsplat reads directly.
"""
import shutil
import subprocess
from pathlib import Path


def _run(cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def run(cfg, paths):
    scfg = cfg["sfm"]
    db = paths.colmap / "database.db"
    if db.exists():
        db.unlink()

    # 1. Feature extraction (GPU SIFT), using masks so only the dish contributes.
    _run([
        "colmap", "feature_extractor",
        "--database_path", db,
        "--image_path", paths.images,
        "--ImageReader.mask_path", paths.masks,
        "--ImageReader.single_camera", 1,
        "--ImageReader.camera_model", scfg["camera_model"],
        "--SiftExtraction.use_gpu", 1,
    ])

    # 2. Matching. Sequential is ideal for video frames; exhaustive is more robust.
    matcher = {
        "sequential": "sequential_matcher",
        "exhaustive": "exhaustive_matcher",
    }[scfg["matcher"]]
    _run(["colmap", matcher, "--database_path", db, "--SiftMatching.use_gpu", 1])

    # 3. Mapping.
    sparse_root = paths.colmap / "sparse"
    if sparse_root.exists():
        shutil.rmtree(sparse_root)
    sparse_root.mkdir(parents=True, exist_ok=True)

    if scfg["use_glomap"]:
        _run([
            "glomap", "mapper",
            "--database_path", db,
            "--image_path", paths.images,
            "--output_path", sparse_root,
        ])
    else:
        _run([
            "colmap", "mapper",
            "--database_path", db,
            "--image_path", paths.images,
            "--output_path", sparse_root,
        ])

    if not (paths.sparse / "cameras.bin").exists() and \
       not (paths.sparse / "cameras.txt").exists():
        raise RuntimeError("SfM produced no model in sparse/0 — too few matches?")
