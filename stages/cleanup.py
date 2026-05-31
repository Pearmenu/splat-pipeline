"""Stage 5 — limpeza automática (poda os floaters/sujeira).

Even with masked training a few stray gaussians survive. We prune in four passes:
  1. opacity:   drop near-transparent gaussians (ghosts/fog)
  2. scale:     drop oversized blobs (the big translucent floaters)
  3. bbox crop: keep only what's inside a percentile spatial box (far floaters)
  4. kNN:       statistical outlier removal (isolated speckles)
Output is a cleaned INRIA-format .ply consumed by the convert stage.
"""
import numpy as np
from plyfile import PlyData, PlyElement
from scipy.spatial import cKDTree


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def run(cfg, paths):
    ccfg = cfg["cleanup"]
    ply = PlyData.read(str(paths.raw_ply))
    v = ply["vertex"].data
    n0 = len(v)

    xyz = np.stack([v["x"], v["y"], v["z"]], axis=1).astype(np.float64)
    opacity = _sigmoid(v["opacity"].astype(np.float64))
    scale = np.exp(np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], axis=1).astype(np.float64))
    scale_size = scale.max(axis=1)

    keep = np.ones(n0, dtype=bool)

    # 1. opacity
    keep &= opacity >= ccfg["opacity_min"]

    # 2. scale (percentile over the currently-kept set)
    if keep.any():
        thr = np.percentile(scale_size[keep], ccfg["scale_max_pct"])
        keep &= scale_size <= thr

    # 3. bbox crop on percentiles of kept points
    if keep.any():
        lo, hi = ccfg["bbox_pct"]
        mn = np.percentile(xyz[keep], lo, axis=0)
        mx = np.percentile(xyz[keep], hi, axis=0)
        inside = np.all((xyz >= mn) & (xyz <= mx), axis=1)
        keep &= inside

    # 4. statistical outlier removal (kNN mean distance)
    if keep.sum() > ccfg["knn_k"] + 1:
        pts = xyz[keep]
        tree = cKDTree(pts)
        d, _ = tree.query(pts, k=ccfg["knn_k"] + 1)  # includes self at d=0
        mean_d = d[:, 1:].mean(axis=1)
        thr = mean_d.mean() + ccfg["knn_std"] * mean_d.std()
        sub_keep = mean_d <= thr
        idx = np.where(keep)[0]
        keep[idx[~sub_keep]] = False

    kept = np.asarray(ply["vertex"].data)[keep]
    PlyData([PlyElement.describe(kept, "vertex")]).write(str(paths.clean_ply))
    print(f"   kept {keep.sum()}/{n0} gaussians ({100 * keep.sum() / n0:.1f}%)")
