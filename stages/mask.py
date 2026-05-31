"""Stage 2 — recortar o prato do fundo (a chave do arquivo limpo).

For each frame we run rembg (salient-object matting, no prompt needed) to get an
alpha matte, harden + erode it to kill edge fringe, then:
  - write the subject composited onto BLACK to frames/images/  (used for training
    and SfM — a uniform background reconstructs as an easily-pruned black void)
  - write a binary mask to frames/masks/  named "<image>.png.png" so COLMAP
    ignores background features (its mask convention is <image_name> + ".png").
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove


def run(cfg, paths):
    mcfg = cfg["mask"]
    session = new_session(mcfg["model"])
    erode = int(mcfg["erode_px"])
    min_area = float(mcfg["min_area_ratio"])

    for d in (paths.images, paths.masks):
        for f in d.glob("*.png"):
            f.unlink()

    frames = sorted(paths.raw_frames.glob("*.png"))
    kept = 0
    for f in frames:
        rgba = remove(Image.open(f).convert("RGB"), session=session)  # PIL RGBA
        rgba = np.asarray(rgba)
        rgb, alpha = rgba[..., :3], rgba[..., 3]

        binary = (alpha > 127).astype(np.uint8)
        if erode > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode * 2 + 1,) * 2)
            binary = cv2.erode(binary, k)

        area_ratio = binary.mean()
        if area_ratio < min_area:
            continue  # subject too small / matting failed for this frame

        composited = rgb * binary[..., None]  # black background
        cv2.imwrite(str(paths.images / f.name),
                    cv2.cvtColor(composited, cv2.COLOR_RGB2BGR))
        # COLMAP mask: filename = imagename + ".png", 0 = ignore, 255 = use
        cv2.imwrite(str(paths.masks / (f.name + ".png")), binary * 255)
        kept += 1

    print(f"   masked {kept}/{len(frames)} frames")
    if kept < 20:
        raise RuntimeError(
            f"only {kept} usable frames after masking — check capture/background")
