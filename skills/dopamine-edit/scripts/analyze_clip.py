#!/usr/bin/env python3
"""Analyze a raw clip for the dopamine-edit pipeline.

Produces analysis.json plus a 12-frame contact sheet and three keyframes.
Only reads the input.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ffprobe(path: Path) -> dict:
    cp = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], timeout=120)
    if cp.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {cp.stderr.strip()}")
    return json.loads(cp.stdout)


def frac(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        a, b = value.split("/", 1)
        try:
            return float(a) / float(b)
        except Exception:  # noqa: BLE001
            return 0.0
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return 0.0


def rotation_of(stream: dict) -> int:
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                return int(float(sd["rotation"]))
            except Exception:  # noqa: BLE001
                pass
    tags = stream.get("tags", {}) or {}
    try:
        return int(float(tags.get("rotate", 0)))
    except Exception:  # noqa: BLE001
        return 0


def detect_scenes(path: Path, duration: float, threshold: float, max_seconds: float) -> list[float]:
    limit = min(duration, max_seconds) if duration else max_seconds
    vf = f"scale=320:-2,select='gt(scene,{threshold})',showinfo"
    cp = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-t", f"{limit:.3f}", "-an", "-vf", vf, "-f", "null", "-",
    ], timeout=max(300, int(limit * 12)))
    cuts: list[float] = []
    for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", cp.stderr):
        t = float(m.group(1))
        if 0.05 < t < limit - 0.05:
            cuts.append(round(t, 3))
    # de-dupe near-identical cuts
    out: list[float] = []
    for t in cuts:
        if not out or t - out[-1] > 0.12:
            out.append(t)
    return out


def contact_sheet(path: Path, out: Path, duration: float, limit: float, frames: int) -> str | None:
    d = max(0.5, min(duration or limit, limit))
    fps = max(frames / d, 0.05)
    out.parent.mkdir(parents=True, exist_ok=True)
    cp = run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-t", f"{d:.3f}",
        "-vf", f"fps={fps:.6f},scale=320:-2,tile=4x3:padding=4:margin=4",
        "-frames:v", "1", "-q:v", "3", str(out),
    ], timeout=300)
    return str(out) if cp.returncode == 0 and out.exists() else None


def keyframes(path: Path, outdir: Path, duration: float, limit: float) -> list[str]:
    d = max(0.2, min(duration or limit, limit))
    outdir.mkdir(parents=True, exist_ok=True)
    outs = []
    for i, frac in enumerate((0.15, 0.5, 0.85), start=1):
        t = max(0.0, min(d - 0.05, d * frac))
        out = outdir / f"key-{i}-{t:.2f}s.png"
        cp = run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", str(out),
        ], timeout=120)
        if cp.returncode == 0 and out.exists():
            outs.append(str(out))
    return outs


def loudness(path: Path, limit: float) -> dict:
    cp = run([
        "ffmpeg", "-hide_banner", "-nostats", "-t", f"{limit:.3f}",
        "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-",
    ], timeout=max(300, int(limit * 8)))
    text = cp.stderr
    integrated = None
    peak = None
    m = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", text)
    if m:
        integrated = float(m[-1])
    m = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", text)
    if m:
        peak = float(m[-1])
    return {"integrated_lufs": integrated, "true_peak_dbfs": peak}


def silences(path: Path, limit: float) -> list[dict]:
    cp = run([
        "ffmpeg", "-hide_banner", "-nostats", "-t", f"{limit:.3f}",
        "-i", str(path), "-af", "silencedetect=noise=-35dB:d=0.35", "-f", "null", "-",
    ], timeout=max(300, int(limit * 8)))
    text = cp.stderr
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", text)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        out.append({"start": round(max(0.0, s), 3), "end": round(e, 3) if e is not None else None})
    return out


def build_shots(duration: float, cuts: list[float], limit: float) -> list[dict]:
    d = min(duration or limit, limit)
    edges = [0.0] + [c for c in cuts if 0 < c < d] + [d]
    shots = []
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        if b - a < 0.08:
            continue
        shots.append({
            "index": len(shots) + 1,
            "start": round(a, 3),
            "end": round(b, 3),
            "duration": round(b - a, 3),
        })
    return shots


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("--out", required=True, help="artifact directory")
    ap.add_argument("--max-seconds", type=float, default=600.0)
    ap.add_argument("--scene-threshold", type=float, default=0.32)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.max_seconds <= 0 or not 0 < args.scene_threshold < 1:
        ap.error('--max-seconds must be positive; scene threshold must be between 0 and 1')

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        print(f"ERROR: not found: {src}", file=sys.stderr)
        return 2

    outdir = Path(args.out).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    probe = ffprobe(src)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        print("ERROR: no video stream", file=sys.stderr)
        return 2

    duration = 0.0
    try:
        duration = float(probe.get("format", {}).get("duration") or video.get("duration") or 0)
    except Exception:  # noqa: BLE001
        duration = 0.0
    limit = min(duration or args.max_seconds, args.max_seconds)

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rot = rotation_of(video)
    if abs(rot) % 180 == 90:
        width, height = height, width

    fps = frac(video.get("avg_frame_rate")) or frac(video.get("r_frame_rate"))
    codec = video.get("codec_name")
    pix_fmt = video.get("pix_fmt")
    has_audio = audio is not None
    channels = int(audio.get("channels") or 0) if audio else 0
    sample_rate = int(audio.get("sample_rate") or 0) if audio else 0

    orientation = "square"
    if width and height:
        if height > width * 1.05:
            orientation = "portrait"
        elif width > height * 1.05:
            orientation = "landscape"
    canvas = {"portrait": "1080x1920", "landscape": "1920x1080", "square": "1080x1080"}[orientation]

    needs_proxy = (
        codec not in {"h264", "hevc", "vp9", "av1"}
        or pix_fmt not in {"yuv420p", "yuvj420p"}
        or abs(rot) % 360 != 0
    )

    print(f"analyzing {src.name} ...", file=sys.stderr)
    cuts = detect_scenes(src, duration, args.scene_threshold, args.max_seconds)
    shots = build_shots(duration, cuts, args.max_seconds)
    contact = contact_sheet(src, outdir / "contact.jpg", duration, args.max_seconds, 12)
    keys = keyframes(src, outdir / "frames", duration, args.max_seconds)

    audio_info = {"has_audio": has_audio, "channels": channels, "sample_rate": sample_rate}
    if has_audio:
        audio_info.update(loudness(src, args.max_seconds))
        audio_info["silences"] = silences(src, args.max_seconds)

    flags = []
    if needs_proxy:
        flags.append("needs_proxy")
    if has_audio and (audio_info.get("integrated_lufs") or 0) < -30:
        flags.append("quiet_audio")
    if has_audio and audio_info.get("true_peak_dbfs") is not None and audio_info['true_peak_dbfs'] > -0.5:
        flags.append("clipping_audio")
    if duration and duration < 3:
        flags.append("very_short")
    if width and width < 720:
        flags.append("low_resolution")
    if fps and fps < 24:
        flags.append("low_fps")

    report = {
        "input": str(src),
        "analyzed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "duration": round(duration, 3),
        "analyzed_seconds": round(limit, 3),
        "width": width,
        "height": height,
        "orientation": orientation,
        "suggested_canvas": canvas,
        "fps": round(fps, 3),
        "codec": codec,
        "pix_fmt": pix_fmt,
        "bit_rate": int(probe.get("format", {}).get("bit_rate") or 0),
        "rotation": rot,
        "size_bytes": src.stat().st_size,
        "needs_proxy": needs_proxy,
        "has_audio": has_audio,
        "audio": audio_info,
        "scene_threshold": args.scene_threshold,
        "cuts": cuts,
        "shots": shots,
        "cut_rate_per_10s": round(len(cuts) / max(limit, 0.1) * 10, 2),
        "longest_shot": round(max((s["duration"] for s in shots), default=limit), 3),
        "contact_sheet": contact,
        "keyframes": keys,
        "flags": flags,
        "notes": [],
    }

    if len(shots) <= 1 and duration > 4:
        report["notes"].append("single continuous shot; plan cutaways, punch-ins, or inserts")
    if not has_audio:
        report["notes"].append("no audio stream; design the sound from scratch")
    if report["longest_shot"] > 4:
        report["notes"].append("long static stretch; add camera motion or cut it")
    if orientation == "landscape" and canvas == "1080x1920":
        report["notes"].append("landscape source needs a reframe/crop for portrait")

    path = outdir / "analysis.json"
    path.write_text(json.dumps(report, indent=2) + "\n")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"duration   {report['duration']}s")
        print(f"format     {width}x{height} @ {fps:.2f}fps {orientation}")
        print(f"shots      {len(shots)} (longest {report['longest_shot']}s)")
        print(f"audio      {'yes' if has_audio else 'no'}"
              + (f" | {audio_info.get('integrated_lufs')} LUFS" if has_audio else ""))
        print(f"flags      {', '.join(flags) or 'none'}")
        print(f"contact    {contact}")
        print(f"json       {path}")
        for n in report["notes"]:
            print(f"note       {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
