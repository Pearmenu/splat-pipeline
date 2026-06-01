"""Stage 1 — extract sharp frames from the video.

ffmpeg pulls frames at a fixed rate; we then drop blurry frames (low Laplacian
variance) and uniformly subsample down to max_frames. Sharp, well-spread frames
make SfM converge faster and cleaner.
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np


def _ffmpeg_extract(video: Path, out_dir: Path, fps: float, max_dim: int = 0):
    for f in out_dir.glob("*.png"):
        f.unlink()
    vf = f"fps={fps}"
    if max_dim and max_dim > 0:
        # Downscale so the long edge <= max_dim (keeps aspect, even dimensions).
        # Speeds up SfM + training a lot; quality impact on a dish is negligible.
        vf += (f",scale='min({max_dim},iw)':'min({max_dim},ih)'"
               f":force_original_aspect_ratio=decrease:force_divisible_by=2")
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf,
        "-qscale:v", "2",
        str(out_dir / "frame_%04d.png"),
    ]
    subprocess.run(cmd, check=True)


def _sharpness(img_path: Path) -> float:
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def run(cfg, paths):
    fcfg = cfg["frames"]
    _ffmpeg_extract(paths.video, paths.raw_frames, fcfg["fps"], fcfg.get("max_dim", 0))

    frames = sorted(paths.raw_frames.glob("*.png"))
    if not frames:
        raise RuntimeError("ffmpeg produced no frames — check the video file")

    # Drop blurry frames.
    scored = [(f, _sharpness(f)) for f in frames]
    sharp = [f for f, s in scored if s >= fcfg["blur_threshold"]]
    if len(sharp) < 20:  # too aggressive — keep the sharpest 20 instead
        sharp = [f for f, _ in sorted(scored, key=lambda x: -x[1])[:20]]
    print(f"   {len(sharp)}/{len(frames)} frames passed the blur filter")

    # Uniformly subsample to the cap (preserves angular coverage).
    cap = fcfg["max_frames"]
    if len(sharp) > cap:
        idx = np.linspace(0, len(sharp) - 1, cap).round().astype(int)
        sharp = [sharp[i] for i in sorted(set(idx))]
        print(f"   subsampled to {len(sharp)} frames")

    keep = {f.name for f in sharp}
    for f in frames:
        if f.name not in keep:
            f.unlink()
