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


def _fit_plane(xyz, iters=300, thresh_frac=0.01):
    """RANSAC: find the dominant plane (the scan-mat). Returns (center, normal, inliers)."""
    n = len(xyz)
    extent = np.linalg.norm(np.percentile(xyz, 97, 0) - np.percentile(xyz, 3, 0))
    thresh = thresh_frac * extent
    best_inl = np.zeros(n, dtype=bool)
    best = (xyz.mean(0), np.array([0.0, 0.0, 1.0]))
    for _ in range(iters):
        i = np.random.choice(n, 3, replace=False)
        p = xyz[i]
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        ln = np.linalg.norm(nrm)
        if ln < 1e-9:
            continue
        nrm = nrm / ln
        inl = np.abs((xyz - p[0]) @ nrm) < thresh
        if inl.sum() > best_inl.sum():
            best_inl, best = inl, (p[0], nrm)
    # refit normal by PCA on the inliers (more accurate than 3 random points)
    pts = xyz[best_inl]
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    return c, vt[-1], best_inl


def _remove_ground(xyz, ccfg):
    """Keep only the dish: the band ABOVE the mat plane, within the dish radius.
    Removes the flat mat+tags (height ~0) and the far backdrop (height/radius large)."""
    c, nrm, inl = _fit_plane(xyz)
    h = (xyz - c) @ nrm                       # signed height off the plane
    ext = np.linalg.norm(np.percentile(xyz, 97, 0) - np.percentile(xyz, 3, 0))
    # orient normal so the dish side (more mass above the slab) is positive
    if (h > 0.05 * ext).sum() < (h < -0.05 * ext).sum():
        nrm, h = -nrm, -h
    proj = (xyz - c) - np.outer(h, nrm)        # in-plane offset from mat center
    rho = np.linalg.norm(proj, axis=1)
    mat_r = np.percentile(rho[inl], 90) if inl.any() else ext  # mat radius = scale ref
    band = ccfg.get("ground_band", 0.03) * mat_r   # skip the mat slab
    h_max = ccfg.get("dish_height", 0.8) * mat_r    # below the backdrop
    r_max = ccfg.get("dish_radius", 1.05) * mat_r   # within the dish footprint
    return (h > band) & (h < h_max) & (rho < r_max)


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

    # 0. ground-plane removal (scan-mat): keep only the dish above the mat plane
    if ccfg.get("ground_removal", False):
        keep &= _remove_ground(xyz, ccfg)
        print(f"   ground-plane removal: {keep.sum()}/{n0} acima da base")

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
