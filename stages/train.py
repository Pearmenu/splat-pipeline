"""Stage 4 — train the Gaussian Splatting model (gsplat, MCMC strategy).

We call gsplat's reference trainer (examples/simple_trainer.py) with the MCMC
densification strategy — it caps the gaussian budget and produces far fewer
floaters than vanilla densification. Then we export the latest checkpoint to a
minimal INRIA-format .ply that the cleanup/convert stages consume.

NOTE: the exact simple_trainer flags can drift between gsplat versions. If the
subprocess errors on an unknown argument, run `python $GSPLAT_DIR/examples/
simple_trainer.py mcmc --help` on the pod and adjust the flags below.
"""
import os
import subprocess
from pathlib import Path

import numpy as np
import torch
from plyfile import PlyData, PlyElement


def _trainer_path() -> Path:
    gsplat_dir = Path(os.environ.get("GSPLAT_DIR", "/opt/gsplat"))
    p = gsplat_dir / "examples" / "simple_trainer.py"
    if not p.exists():
        raise RuntimeError(f"gsplat trainer not found at {p} (set GSPLAT_DIR)")
    return p


def _link_images(paths):
    """gsplat's COLMAP parser expects data_dir/images + data_dir/sparse/0."""
    link = paths.colmap / "images"
    if link.exists() or link.is_symlink():
        return
    try:
        link.symlink_to(paths.images.resolve())
    except OSError:
        import shutil
        shutil.copytree(paths.images, link)


def _latest_ckpt(result_dir: Path) -> Path:
    ckpts = sorted(result_dir.rglob("*.pt"), key=lambda p: p.stat().st_mtime)
    if not ckpts:
        raise RuntimeError(f"no checkpoint produced under {result_dir}")
    return ckpts[-1]


def _export_ply(ckpt_path: Path, ply_path: Path):
    ck = torch.load(ckpt_path, map_location="cpu")
    sp = ck.get("splats", ck)

    means = sp["means"].float().numpy()                  # [N,3]
    scales = sp["scales"].float().numpy()                # [N,3] (log)
    quats = sp["quats"].float().numpy()                  # [N,4] (raw)
    opac = sp["opacities"].float().numpy().reshape(-1)   # [N]  (logit)
    f_dc = sp["sh0"].float().numpy().reshape(means.shape[0], -1)  # [N,3]

    n = means.shape[0]
    fields = [("x", "f4"), ("y", "f4"), ("z", "f4"),
              ("nx", "f4"), ("ny", "f4"), ("nz", "f4"),
              ("f_dc_0", "f4"), ("f_dc_1", "f4"), ("f_dc_2", "f4"),
              ("opacity", "f4"),
              ("scale_0", "f4"), ("scale_1", "f4"), ("scale_2", "f4"),
              ("rot_0", "f4"), ("rot_1", "f4"), ("rot_2", "f4"), ("rot_3", "f4")]
    arr = np.zeros(n, dtype=fields)
    arr["x"], arr["y"], arr["z"] = means.T
    arr["f_dc_0"], arr["f_dc_1"], arr["f_dc_2"] = f_dc.T
    arr["opacity"] = opac
    arr["scale_0"], arr["scale_1"], arr["scale_2"] = scales.T
    arr["rot_0"], arr["rot_1"], arr["rot_2"], arr["rot_3"] = quats.T

    PlyData([PlyElement.describe(arr, "vertex")]).write(str(ply_path))
    print(f"   exported {n} gaussians -> {ply_path.name}")


def run(cfg, paths):
    tcfg = cfg["train"]
    _link_images(paths)

    cmd = [
        "python", str(_trainer_path()), "mcmc",
        "--data_dir", str(paths.colmap),
        "--result_dir", str(paths.train),
        "--data_factor", str(tcfg["data_factor"]),
        "--max_steps", str(tcfg["iters"]),
        "--sh_degree", str(tcfg["sh_degree"]),
        "--strategy.cap-max", str(tcfg["cap_max"]),
        "--disable_viewer",
    ]
    print("   $", " ".join(cmd))
    subprocess.run(cmd, check=True)

    _export_ply(_latest_ckpt(paths.train), paths.raw_ply)
