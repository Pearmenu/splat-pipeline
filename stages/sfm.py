"""Stage 3 — camera poses via Structure from Motion.

COLMAP extracts + matches features (masked, so background is ignored), then
GLOMAP solves the global reconstruction (much faster than COLMAP's incremental
mapper). Output is a sparse model in colmap/sparse/0 that gsplat reads directly.
"""
import os
import shutil
import subprocess
from pathlib import Path

# COLMAP/GLOMAP come from the micromamba prefix; their shared libs (libfaiss, etc.)
# live in <prefix>/lib, which isn't on LD_LIBRARY_PATH. Add it ONLY for these
# subprocess calls so it doesn't clash with torch's libs in the training stage.
_COLMAP_LIB = "/opt/splattools/lib"


def _run(cmd):
    print("   $", " ".join(str(c) for c in cmd))
    env = os.environ.copy()
    if os.path.isdir(_COLMAP_LIB):
        env["LD_LIBRARY_PATH"] = _COLMAP_LIB + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    subprocess.run([str(c) for c in cmd], check=True, env=env)


def run(cfg, paths):
    scfg = cfg["sfm"]
    db = paths.colmap / "database.db"
    if db.exists():
        db.unlink()

    # With the PeAR scan mat, the FULL frame (tags + mat texture) gives rock-solid
    # features -> great poses, even for a glossy plate. So SfM runs on the RAW frames
    # (no mask). Training still uses the masked dish-only images (same filenames),
    # so gsplat reconstructs only the dish. Without the mat, fall back to masked SfM.
    use_mat = scfg.get("use_mat", False)
    img_dir = paths.raw_frames if use_mat else paths.images

    # 1. Feature extraction (GPU SIFT by default in COLMAP).
    fe = [
        "colmap", "feature_extractor",
        "--database_path", db,
        "--image_path", img_dir,
        "--ImageReader.single_camera", 1,
        "--ImageReader.camera_model", scfg["camera_model"],
    ]
    if not use_mat:
        fe += ["--ImageReader.mask_path", paths.masks]
    _run(fe)

    # 2. Matching. Sequential is ideal for video frames; exhaustive is more robust.
    matcher = {
        "sequential": "sequential_matcher",
        "exhaustive": "exhaustive_matcher",
    }[scfg["matcher"]]
    _run(["colmap", matcher, "--database_path", db])

    # 3. Mapping.
    sparse_root = paths.colmap / "sparse"
    if sparse_root.exists():
        shutil.rmtree(sparse_root)
    sparse_root.mkdir(parents=True, exist_ok=True)

    if scfg["use_glomap"]:
        _run([
            "glomap", "mapper",
            "--database_path", db,
            "--image_path", img_dir,
            "--output_path", sparse_root,
        ])
    else:
        _run([
            "colmap", "mapper",
            "--database_path", db,
            "--image_path", img_dir,
            "--output_path", sparse_root,
        ])

    if not (paths.sparse / "cameras.bin").exists() and \
       not (paths.sparse / "cameras.txt").exists():
        raise RuntimeError("SfM produced no model in sparse/0 — too few matches?")
