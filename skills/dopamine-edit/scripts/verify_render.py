#!/usr/bin/env python3
"""Verify an encoded delivery against explicit expectations; no creative pass implied."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def number(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result if math.isfinite(result) else math.nan


def rate(value) -> float:
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return math.nan


def expectations(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError('DELIVERY.json must be an object')
    for key in ('duration', 'width', 'height', 'fps'):
        if isinstance(data.get(key), bool) or not isinstance(data.get(key), (int, float)) or not number(data.get(key)) > 0:
            raise ValueError(f'{key} must be finite and positive')
    for key in ('width', 'height'):
        if not isinstance(data[key], int):
            raise ValueError(f'{key} must be an integer')
    if not isinstance(data.get('expect_audio'), bool):
        raise ValueError('expect_audio must be explicitly true or false')
    if 'expect_music' not in data:
        if data.get('legacy_project') is not True:
            raise ValueError('new delivery plans must state expect_music true or false '
                             '(legacy_project:true only for projects created before music gating)')
    elif not isinstance(data['expect_music'], bool):
        raise ValueError('expect_music must be boolean')
    else:
        if data['expect_music'] and not data['expect_audio']:
            raise ValueError('required music conflicts with silent delivery')
        if not data['expect_music'] and not str(data.get('music_exception', '')).strip():
            raise ValueError('expect_music false requires a documented music_exception')
    if 'expect_brand' not in data:
        if data.get('legacy_project') is not True:
            raise ValueError('new delivery plans must state expect_brand true or false '
                             '(legacy_project:true only for projects created before brand gating)')
    elif not isinstance(data['expect_brand'], bool):
        raise ValueError('expect_brand must be boolean')
    for key, default in (('target_lufs', -14), ('lufs_tolerance', 2), ('max_true_peak_dbtp', -1)):
        data.setdefault(key, default)
        if isinstance(data[key], bool) or not isinstance(data[key], (int, float)) or not math.isfinite(number(data[key])):
            raise ValueError(f'{key} must be finite')
    if not 0 <= data['lufs_tolerance'] <= 3 or data['max_true_peak_dbtp'] > -1:
        raise ValueError('invalid loudness tolerance or true-peak ceiling')
    return data


def invoke(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def verify(video: Path, expected: dict, report: Path, proof_dir: Path) -> dict:
    data = {'ok': False, 'video': str(video), 'sha256': None,
            'expected': expected, 'failures': [], 'warnings': [], 'measurements': {}}
    failures, warnings, measured = data['failures'], data['warnings'], data['measurements']
    if not video.is_file() or video.stat().st_size == 0:
        failures.append('missing_or_empty_video')
        return data
    data['sha256'] = digest(video)
    cp = invoke(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)], 120)
    if cp.returncode:
        failures.append('probe_failed')
        data['probe_error'] = cp.stderr[-4000:]
        return data
    probe = json.loads(cp.stdout)
    probe_path = report.with_name(report.stem + '-probe.json')
    probe_path.write_text(json.dumps(probe, indent=2) + '\n')
    data['probe'] = str(probe_path)
    streams = probe.get('streams', [])
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if v is None:
        failures.append('missing_video_stream')
        return data
    duration = number(probe.get('format', {}).get('duration'))
    fps = rate(v.get('avg_frame_rate'))
    measured.update(duration=duration if math.isfinite(duration) else None,
                    fps=fps if math.isfinite(fps) else None,
                    width=v.get('width'), height=v.get('height'), has_audio=a is not None,
                    size_bytes=video.stat().st_size)
    tolerance = max(0.1, 2 / expected['fps'])
    if not math.isfinite(duration) or abs(duration - expected['duration']) > tolerance:
        failures.append('duration_mismatch')
    if v.get('width') != expected['width'] or v.get('height') != expected['height']:
        failures.append('dimensions_mismatch')
    if not math.isfinite(fps) or abs(fps - expected['fps']) > 0.02:
        failures.append('fps_mismatch')
    if v.get('codec_name') != 'h264' or v.get('pix_fmt') != 'yuv420p':
        failures.append('delivery_video_codec_or_pixel_format')
    if 'mp4' not in probe.get('format', {}).get('format_name', '').split(','):
        failures.append('not_mp4_container')
    if expected['expect_audio'] and a is None:
        failures.append('missing_audio_stream')
    if a:
        if a.get('codec_name') != 'aac':
            failures.append('delivery_audio_not_aac')
        vd, ad = number(v.get('duration')), number(a.get('duration'))
        vs, aus = number(v.get('start_time')), number(a.get('start_time'))
        if all(math.isfinite(x) for x in (vd, ad)):
            measured['audio_video_duration_delta'] = round(ad - vd, 6)
            if abs(ad - vd) > 0.15:
                failures.append('audio_video_duration_mismatch')
        if all(math.isfinite(x) for x in (vd, ad, vs, aus)) and abs((aus + ad) - (vs + vd)) > 0.15:
            failures.append('audio_video_end_mismatch')
    timeout = max(180, int(expected['duration'] * 20))
    cp = invoke(['ffmpeg', '-nostdin', '-hide_banner', '-v', 'error', '-xerror',
                 '-err_detect', 'explode', '-i', str(video), '-map', '0:v:0',
                 '-map', '0:a:0?', '-f', 'null', '-'], timeout)
    if cp.returncode or cp.stderr.strip():
        failures.append('decode_errors')
        data['decode_error'] = cp.stderr[-4000:]
    if a and expected['expect_audio']:
        cp = invoke(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(video), '-vn',
                     '-af', 'loudnorm=I=-14:TP=-1:LRA=11:print_format=json', '-f', 'null', '-'], timeout)
        blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', cp.stderr)
        if cp.returncode or not blocks:
            failures.append('audio_measurement_failed')
        else:
            audio = json.loads(blocks[-1])
            loudness, peak = number(audio.get('input_i')), number(audio.get('input_tp'))
            measured['audio'] = audio
            if not math.isfinite(loudness) or loudness <= -60:
                failures.append('audio_silent_or_unmeasurable')
            elif abs(loudness - expected['target_lufs']) > expected['lufs_tolerance']:
                failures.append('master_loudness_out_of_range')
            if not math.isfinite(peak) or peak > expected['max_true_peak_dbtp'] + 0.2:
                failures.append('true_peak_out_of_range')
    elif a:
        warnings.append('audio_stream_present_in_silent_delivery_review_for_unintended_sound')
    cp = invoke(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(video), '-an',
                 '-vf', 'blackdetect=d=0.1:pix_th=0.10:pic_th=0.98', '-f', 'null', '-'], timeout)
    black = [{'start': float(s), 'end': float(e), 'duration': float(d)}
             for s, e, d in re.findall(r'black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)', cp.stderr)]
    measured['near_black_intervals'] = black
    if cp.returncode:
        failures.append('black_analysis_failed')
    if any(b['start'] <= 1 / expected['fps'] for b in black):
        failures.append('black_opening')
    if math.isfinite(duration) and sum(b['duration'] for b in black) >= duration * .95:
        failures.append('almost_entirely_black')
    if black:
        warnings.append('near_black_intervals_require_visual_review')
    # Extract exact samples individually: very short clips still fill all 8 cells.
    if math.isfinite(duration) and duration > 0:
        proof_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        last = max(0, duration - 1 / expected['fps'])
        for i in range(8):
            t = last * i / 7
            frame = proof_dir / f'frame-{i + 1:02d}.jpg'
            cp = invoke(['ffmpeg', '-nostdin', '-y', '-hide_banner', '-v', 'error',
                         '-ss', f'{t:.6f}', '-i', str(video), '-frames:v', '1', '-q:v', '2', str(frame)], 120)
            if cp.returncode or not frame.is_file() or frame.stat().st_size == 0:
                failures.append(f'proof_frame_{i + 1}_failed')
            else:
                frames.append({'path': str(frame), 'time': round(t, 6)})
        data['frames'] = frames
        if len(frames) == 8:
            sheet = proof_dir / 'contact.jpg'
            cp = invoke(['ffmpeg', '-nostdin', '-y', '-hide_banner', '-v', 'error',
                         '-framerate', '1', '-i', str(proof_dir / 'frame-%02d.jpg'),
                         '-vf', 'scale=360:-2,tile=4x2:padding=6:margin=6',
                         '-frames:v', '1', '-q:v', '3', str(sheet)], 120)
            if cp.returncode or not sheet.is_file() or not sheet.stat().st_size:
                failures.append('contact_sheet_failed')
            else:
                data.update(cover=frames[0]['path'], contact=str(sheet))
    data['ok'] = not failures
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video')
    ap.add_argument('--expect', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--proof-dir', required=True)
    args = ap.parse_args()
    video, report = Path(args.video).resolve(), Path(args.report).resolve()
    if report == video or report == Path(args.expect).resolve():
        ap.error('report must not overwrite video or expectations')
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        expected = expectations(Path(args.expect))
        result = verify(video, expected, report, Path(args.proof_dir).resolve())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {'ok': False, 'video': str(video), 'failures': ['verification_failed'], 'error': str(exc)}
    tmp = report.with_suffix(report.suffix + '.tmp')
    tmp.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, report)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
