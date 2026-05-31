"""RunPod serverless handler — wraps pipeline.py for the PeAR backend.

Input event:
  {
    "input": {
      "video_url":     "https://.../input.mp4",   # presigned/public GET
      "splat_put_url": "https://.../x.splat?...",  # presigned R2 PUT
      "splat_headers": {"Content-Type": "..."},
      "ply_put_url":   "https://.../x.ply?...",     # optional
      "ply_headers":   {"Content-Type": "..."}
    }
  }

Returns: {"ok": true, "size_bytes": <int>, "gaussians": <int|null>}
RunPod POSTs this result to the webhook URL configured by the caller.
"""
import re
import subprocess
import tempfile
from pathlib import Path

import requests
import runpod

PIPELINE = "/workspace/pipeline.py"


def _download(url: str, dest: Path):
    with requests.get(url, stream=True, timeout=900) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)


def _put(url: str, headers: dict, path: Path):
    with open(path, "rb") as f:
        r = requests.put(url, data=f, headers=headers or {}, timeout=900)
    r.raise_for_status()


def _gaussian_count(log: str):
    m = re.findall(r"wrote model\.splat: (\d+) gaussians", log)
    return int(m[-1]) if m else None


def handler(event):
    inp = event.get("input", {})
    work = Path(tempfile.mkdtemp(prefix="splatjob_"))
    video = work / "input.mp4"
    run_dir = work / "run"

    _download(inp["video_url"], video)

    proc = subprocess.run(
        ["python", PIPELINE, "--video", str(video), "--workdir", str(run_dir)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "pipeline_failed")[-1500:]}

    splat = run_dir / "out" / "model.splat"
    ply = run_dir / "out" / "model.ply"
    if not splat.exists():
        return {"ok": False, "error": "no_splat_produced"}

    _put(inp["splat_put_url"], inp.get("splat_headers", {}), splat)
    if inp.get("ply_put_url") and ply.exists():
        _put(inp["ply_put_url"], inp.get("ply_headers", {}), ply)

    return {
        "ok": True,
        "size_bytes": splat.stat().st_size,
        "gaussians": _gaussian_count(proc.stdout),
    }


runpod.serverless.start({"handler": handler})
