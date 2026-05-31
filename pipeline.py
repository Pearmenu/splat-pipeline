#!/usr/bin/env python3
"""PeAR Splat Pipeline — orchestrates video -> clean .splat.

Runs six stages in order. Each stage reads/writes a shared work directory so
you can resume from any stage with --from-stage for debugging.
"""
import argparse
import sys
import time
from pathlib import Path

import yaml

from stages import extract_frames, mask, sfm, train, cleanup, convert

STAGES = [
    ("extract_frames", extract_frames.run),
    ("mask", mask.run),
    ("sfm", sfm.run),
    ("train", train.run),
    ("cleanup", cleanup.run),
    ("convert", convert.run),
]


class Paths:
    """Canonical layout of the work directory, shared across stages."""

    def __init__(self, workdir: Path, video: Path):
        self.workdir = workdir
        self.video = video
        self.raw_frames = workdir / "frames" / "raw"      # ffmpeg output
        self.images = workdir / "frames" / "images"       # masked (black bg) -> training + colmap
        self.masks = workdir / "frames" / "masks"         # binary masks for colmap
        self.colmap = workdir / "colmap"                  # database.db + sparse/0
        self.sparse = workdir / "colmap" / "sparse" / "0"
        self.train = workdir / "train"                    # gsplat result dir
        self.raw_ply = workdir / "train" / "model_raw.ply"   # exported from ckpt
        self.out = workdir / "out"
        self.clean_ply = workdir / "out" / "model_clean.ply"
        self.out_splat = workdir / "out" / "model.splat"
        self.out_ply = workdir / "out" / "model.ply"

        for d in (self.raw_frames, self.images, self.masks, self.colmap,
                  self.train, self.out):
            d.mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description="PeAR splat pipeline")
    ap.add_argument("--video", required=True, type=Path, help="input video file")
    ap.add_argument("--workdir", required=True, type=Path, help="work/output directory")
    ap.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml")
    ap.add_argument("--from-stage", choices=[s[0] for s in STAGES],
                    help="resume starting at this stage (assumes earlier outputs exist)")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"video not found: {args.video}")

    cfg = yaml.safe_load(args.config.read_text())
    paths = Paths(args.workdir, args.video)

    start_idx = 0
    if args.from_stage:
        start_idx = [s[0] for s in STAGES].index(args.from_stage)

    print(f"== PeAR splat pipeline ==\n  video:   {args.video}\n  workdir: {args.workdir}\n")
    for name, fn in STAGES[start_idx:]:
        t0 = time.time()
        print(f"-> [{name}] start")
        fn(cfg, paths)
        print(f"<- [{name}] done in {time.time() - t0:.1f}s\n")

    print(f"Done.\n  .splat: {paths.out_splat}\n  .ply:   {paths.out_ply}")


if __name__ == "__main__":
    main()
