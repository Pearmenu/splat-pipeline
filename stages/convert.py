"""Stage 6 — export final assets.

Writes the canonical `.splat` (antimatter15 / PlayCanvas packed format, 32 bytes
per gaussian) that the PeAR viewer uses, plus a copy of the cleaned `.ply`.

.splat layout per gaussian (little-endian):
  position : 3 x float32   (12 bytes)
  scale    : 3 x float32   (12 bytes)  -- linear (exp of stored log-scale)
  color    : 4 x uint8      (4 bytes)  -- RGBA, A = sigmoid(opacity)
  rotation : 4 x uint8      (4 bytes)  -- normalized quat mapped to [0,255]
"""
import shutil

import numpy as np
from plyfile import PlyData

SH_C0 = 0.28209479177387814  # 0th-order spherical harmonic constant


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _adjust_color(rgb, brightness=1.0, contrast=1.0, saturation=1.0):
    """Make the food pop: brightness, then contrast around mid-gray, then saturation."""
    if brightness != 1.0:
        rgb = rgb * brightness
    if contrast != 1.0:
        rgb = (rgb - 0.5) * contrast + 0.5
    if saturation != 1.0:
        lum = (rgb * np.array([0.299, 0.587, 0.114], dtype=np.float32)).sum(axis=1, keepdims=True)
        rgb = lum + (rgb - lum) * saturation
    return rgb


def ply_to_splat(ply_path, splat_path, brightness=1.0, contrast=1.0,
                 saturation=1.0, opacity_boost=1.0):
    v = PlyData.read(str(ply_path))["vertex"]

    xyz = np.stack([v["x"], v["y"], v["z"]], axis=1).astype(np.float32)
    scale = np.exp(np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], axis=1).astype(np.float32))

    quat = np.stack([v["rot_0"], v["rot_1"], v["rot_2"], v["rot_3"]], axis=1).astype(np.float32)
    quat /= np.linalg.norm(quat, axis=1, keepdims=True) + 1e-9

    f_dc = np.stack([v["f_dc_0"], v["f_dc_1"], v["f_dc_2"]], axis=1).astype(np.float32)
    rgb = 0.5 + SH_C0 * f_dc
    rgb = np.clip(_adjust_color(rgb, brightness, contrast, saturation), 0.0, 1.0)
    alpha = _sigmoid(v["opacity"].astype(np.float32))
    if opacity_boost != 1.0:  # push semi-transparent gaussians toward opaque (kills the "see-through" look)
        alpha = np.clip(alpha * opacity_boost, 0.0, 1.0)
    rgba = np.clip(np.concatenate([rgb, alpha[:, None]], axis=1) * 255, 0, 255).astype(np.uint8)

    rot_u8 = np.clip(quat * 128 + 128, 0, 255).astype(np.uint8)

    # Render order: largest, most-opaque first (matches the standard converter).
    importance = scale.prod(axis=1) * alpha
    order = np.argsort(-importance)

    out = np.zeros(len(xyz), dtype=[
        ("pos", "<f4", 3), ("scale", "<f4", 3),
        ("rgba", "u1", 4), ("rot", "u1", 4),
    ])
    out["pos"] = xyz[order]
    out["scale"] = scale[order]
    out["rgba"] = rgba[order]
    out["rot"] = rot_u8[order]
    out.tofile(str(splat_path))
    return len(xyz)


def run(cfg, paths):
    ecfg = cfg["export"]
    formats = ecfg["formats"]

    if "splat" in formats:
        n = ply_to_splat(
            paths.clean_ply, paths.out_splat,
            brightness=ecfg.get("brightness", 1.0),
            contrast=ecfg.get("contrast", 1.0),
            saturation=ecfg.get("saturation", 1.0),
            opacity_boost=ecfg.get("opacity_boost", 1.0),
        )
        mb = paths.out_splat.stat().st_size / 1e6
        print(f"   wrote {paths.out_splat.name}: {n} gaussians, {mb:.1f} MB")

    if "ply" in formats:
        shutil.copyfile(paths.clean_ply, paths.out_ply)
        mb = paths.out_ply.stat().st_size / 1e6
        print(f"   wrote {paths.out_ply.name}: {mb:.1f} MB")
