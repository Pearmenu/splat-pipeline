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
from tqdm import tqdm


def _refine_mask(alpha, mcfg):
    """Turn the BiRefNet alpha into a clean PLATE+FOOD mask.

    BiRefNet gives the food high confidence but the flat/glossy plate LOW
    confidence, so a 127 threshold cuts the plate off. We threshold low to catch
    the plate, close gaps so plate+food fuse into one blob, keep only the largest
    blob (drops stray background), fill interior holes, then grow a touch.
    """
    thr = int(mcfg.get("threshold", 40))
    binary = (alpha > thr).astype(np.uint8)

    close_px = int(mcfg.get("close_px", 7))
    if close_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px * 2 + 1,) * 2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)

    if mcfg.get("keep_largest", True):
        n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        if n > 1:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            binary = (labels == largest).astype(np.uint8)

    if mcfg.get("fill_holes", True):
        h, w = binary.shape
        ff = (binary * 255).astype(np.uint8)
        m = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(ff, m, (0, 0), 255)        # flood background from a corner
        holes = (ff == 0).astype(np.uint8)        # what's still 0 = interior holes
        binary = (binary | holes).astype(np.uint8)

    dilate_px = int(mcfg.get("dilate_px", 0))
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1,) * 2)
        binary = cv2.dilate(binary, k)
    erode_px = int(mcfg.get("erode_px", 0))
    if erode_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px * 2 + 1,) * 2)
        binary = cv2.erode(binary, k)
    return binary


def run(cfg, paths):
    mcfg = cfg["mask"]
    # Prefer the GPU — BiRefNet on CPU is ~40s/frame; on GPU it's <1s/frame.
    # If onnxruntime can't load the CUDA provider it silently falls back to CPU.
    providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                 if mcfg.get("use_gpu", True) else ["CPUExecutionProvider"])
    session = new_session(mcfg["model"], providers=providers)
    try:
        active = session.inner_session.get_providers()
        print(f"   rembg providers ativos: {active}")
        if "CUDAExecutionProvider" not in active:
            print("   ⚠️  recorte na CPU (lento). Verifique onnxruntime-gpu/LD_LIBRARY_PATH.")
    except Exception:
        pass
    min_area = float(mcfg["min_area_ratio"])

    for d in (paths.images, paths.masks):
        for f in d.glob("*.png"):
            f.unlink()

    frames = sorted(paths.raw_frames.glob("*.png"))
    kept = 0
    for f in tqdm(frames, desc="   mask", unit="frame"):
        rgba = remove(Image.open(f).convert("RGB"), session=session)  # PIL RGBA
        rgba = np.asarray(rgba)
        rgb, alpha = rgba[..., :3], rgba[..., 3]

        binary = _refine_mask(alpha, mcfg)

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
