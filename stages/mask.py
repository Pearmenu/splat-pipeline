"""Stage 2 — recortar prato+comida do fundo (a chave do arquivo limpo).

Two masking modes (config `mask.mode`):
  - birefnet (default): rembg salient-object matting. Great for the FOOD, but it
    treats a flat/glossy PLATE as background and drops it.
  - chroma: key out a solid background color (auto-sampled from the frame corners,
    or given explicitly via `chroma_color`). KEEPS the plate — use this when you
    film on a solid contrasting backdrop + base (green is safest: plates/food are
    rarely green). This is the reliable, production mode.

Both paths then: close gaps -> keep largest blob -> fill holes -> optional
dilate/erode, composite the subject onto BLACK (for training + SfM) and write a
COLMAP mask (filename = imagename + ".png", 0 = ignore).
"""
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm


def _clean_binary(binary, mcfg):
    """Close gaps, keep the largest blob, fill holes, optional grow/shrink."""
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
        cv2.floodFill(ff, m, (0, 0), 255)         # flood background from a corner
        holes = (ff == 0).astype(np.uint8)         # what's still 0 = interior holes
        binary = (binary | holes).astype(np.uint8)

    if mcfg.get("convex_hull", False):
        # A plate is convex: take the convex hull of the biggest blob to fill ALL
        # holes (glossy reflections) and smooth the ragged SAM boundary into a clean
        # plate outline. Robust to SAM dropping interior/reflection patches.
        cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            hull = cv2.convexHull(max(cnts, key=cv2.contourArea))
            out = np.zeros_like(binary)
            cv2.fillConvexPoly(out, hull, 1)
            binary = out

    dilate_px = int(mcfg.get("dilate_px", 0))
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1,) * 2)
        binary = cv2.dilate(binary, k)
    erode_px = int(mcfg.get("erode_px", 0))
    if erode_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px * 2 + 1,) * 2)
        binary = cv2.erode(binary, k)
    return binary


def _bg_color(rgb, mcfg):
    """Background color for chroma keying: explicit [r,g,b] or median of the corners."""
    c = mcfg.get("chroma_color", "auto")
    if c not in (None, "auto"):
        return np.array(c, dtype=np.float32)
    h, w, _ = rgb.shape
    s = max(8, min(h, w) // 20)
    corners = np.concatenate([
        rgb[:s, :s].reshape(-1, 3), rgb[:s, -s:].reshape(-1, 3),
        rgb[-s:, :s].reshape(-1, 3), rgb[-s:, -s:].reshape(-1, 3),
    ])
    return np.median(corners.astype(np.float32), axis=0)


def run(cfg, paths):
    mcfg = cfg["mask"]
    mode = mcfg.get("mode", "birefnet")
    min_area = float(mcfg["min_area_ratio"])
    print(f"   modo de máscara: {mode}")

    session = None
    remove = Image = None
    if mode == "birefnet":
        from rembg import new_session, remove as _remove
        from PIL import Image as _Image
        remove, Image = _remove, _Image
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

    sam_model = None
    if mode == "sam":
        # Object-aware segmentation: we prompt SAM with a box around the center
        # (turntable = dish centered) so it returns the WHOLE object — plate + food —
        # instead of just the salient food. This is the "teach it it's a plate" path.
        from ultralytics import SAM
        sam_model = SAM(mcfg.get("sam_model", "sam2.1_b.pt"))
        print(f"   SAM model: {mcfg.get('sam_model', 'sam2.1_b.pt')}")

    for d in (paths.images, paths.masks):
        for f in d.glob("*.png"):
            f.unlink()

    frames = sorted(paths.raw_frames.glob("*.png"))
    kept = 0
    for f in tqdm(frames, desc="   mask", unit="frame"):
        rgb = cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2RGB)

        if mode == "chroma":
            bg = _bg_color(rgb, mcfg)
            tol = float(mcfg.get("chroma_tol", 60))
            dist = np.linalg.norm(rgb.astype(np.float32) - bg, axis=2)
            raw = (dist > tol).astype(np.uint8)            # keep what's NOT the background
        elif mode == "sam":
            h, w = rgb.shape[:2]
            mg = float(mcfg.get("sam_box_margin", 0.12))
            box = [w * mg, h * mg, w * (1 - mg), h * (1 - mg)]  # central box = "the object is here"
            res = sam_model(rgb, bboxes=[box], verbose=False)
            if res and res[0].masks is not None and len(res[0].masks.data):
                raw = (res[0].masks.data[0].cpu().numpy() > 0.5).astype(np.uint8)
            else:
                raw = np.zeros(rgb.shape[:2], np.uint8)
        else:
            rgba = np.asarray(remove(Image.fromarray(rgb), session=session))
            raw = (rgba[..., 3] > int(mcfg.get("threshold", 40))).astype(np.uint8)

        binary = _clean_binary(raw, mcfg)
        if binary.mean() < min_area:
            continue  # subject too small / keying failed for this frame

        composited = rgb * binary[..., None]  # black background
        cv2.imwrite(str(paths.images / f.name), cv2.cvtColor(composited, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(paths.masks / (f.name + ".png")), binary * 255)
        kept += 1

    print(f"   masked {kept}/{len(frames)} frames")
    if kept < 20:
        raise RuntimeError(
            f"only {kept} usable frames after masking — check capture/background")
