#!/usr/bin/env python3
"""Find/download mood-matched, attributed public music; verify its timeline use.

Built-in provider: Kevin MacLeod's Incompetech catalog (CC BY 4.0 when the
current source page still declares that license). No account or paid API.
Search ranks metadata, not audio quality; the editing agent chooses the track.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

CATALOG = 'https://incompetech.com/music/royalty-free/pieces.json'
PAGE = 'https://incompetech.com/music/royalty-free/music.html'
LICENSE = 'https://creativecommons.org/licenses/by/4.0/'
MAX_BYTES = 80 * 1024 * 1024
VOCALS = re.compile(r'\b(vocals?|vocalists?|voices?|singing|lyrics?|choirs?|choral)\b', re.I)
NEGATED = re.compile(r'\b(no|without|not|never|free of|free from)\s+(?:\w+\s+){0,2}$', re.I)
APPROVED_LICENSES = {'CC0', 'CC BY 3.0', 'CC BY 4.0', 'public-domain', 'user-authorized'}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
        temp = stream.name
    os.replace(temp, path)


def public_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'incompetech.com', 'www.incompetech.com'}:
        raise ValueError('built-in downloader only accepts HTTPS Incompetech URLs')
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('credentials or custom ports are not accepted')
    return url


def fetch(url, destination=None, max_bytes=MAX_BYTES):
    """Bounded public download, no cookie jar, exec hooks, or private credentials."""
    public_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'dopamine-edit/1.0 (public licensed music)'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=20) as response:
        public_url(response.geturl())
        if int(response.headers.get('Content-Length', 0)) > max_bytes:
            raise ValueError('download exceeds size limit')
        output = destination.open('xb') if destination else None
        blocks, size = [], 0
        try:
            while True:
                block = response.read(64 * 1024)
                if not block:
                    break
                size += len(block)
                if size > max_bytes or time.monotonic() - started > 90:
                    raise ValueError('download exceeded size/time budget')
                if output:
                    output.write(block)
                else:
                    blocks.append(block)
        finally:
            if output:
                output.close()
    return b''.join(blocks) if destination is None else size


def catalog(refresh=False):
    cache = Path(os.environ.get('DOPAMINE_CACHE_DIR', str(Path.home()/'.cache/dopamine-edit')))/'music/catalog.json'
    if not refresh and cache.is_file() and time.time() - cache.stat().st_mtime < 7 * 86400:
        data = json.loads(cache.read_text())
    else:
        data = json.loads(fetch(CATALOG, max_bytes=8 * 1024 * 1024))
        if not isinstance(data, list) or not data:
            raise ValueError('provider returned an invalid/empty catalog')
        write_json(cache, data)
    if not isinstance(data, list):
        raise ValueError('invalid cached catalog')
    return data


def seconds(value):
    try:
        parts = [float(x) for x in str(value).split(':')]
        return sum(x * 60 ** i for i, x in enumerate(reversed(parts)))
    except ValueError:
        return 0


def vocal_declaration(item):
    """Metadata declares singing; description mentions only when not negated."""
    instruments = str(item.get('instruments') or '')
    match = VOCALS.search(instruments)
    if match:
        return match.group(0)
    description = str(item.get('description') or '')
    for hit in VOCALS.finditer(description):
        if not NEGATED.search(description[max(0, hit.start() - 30):hit.start()]):
            return hit.group(0)
    return None


def rank(items, query, duration, bpm_min=0, bpm_max=250):
    tokens = set(re.findall(r'[a-z]{3,}', query.lower())) - {'music', 'background', 'instrumental', 'video'}
    results = []
    for item in items:
        if vocal_declaration(item):
            continue
        length = seconds(item.get('length'))
        if length < duration:
            continue
        try:
            bpm = float(item.get('bpm') or 0)
        except (ValueError, TypeError):
            bpm = 0
        if bpm and not bpm_min <= bpm <= bpm_max:
            continue
        text = ' '.join(str(item.get(k) or '') for k in ('title', 'instruments', 'description', 'feel')).lower()
        matched = sorted(t for t in tokens if t in text)
        if not matched:
            continue
        feel = str(item.get('feel', '')).lower()
        score = sum(3 if t in feel else 1 for t in matched)
        results.append({'id': item.get('isrc'), 'title': item.get('title'), 'artist': 'Kevin MacLeod',
                        'duration': length, 'bpm': bpm or None, 'instruments': item.get('instruments'),
                        'feel': item.get('feel'), 'description': item.get('description'),
                        'score': score, 'matched': matched,
                        'source_url': PAGE, 'license_to_verify': LICENSE})
    return sorted(results, key=lambda r: (-r['score'], r['title'] or ''))


def run(args, timeout=180):
    cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if cp.returncode:
        raise ValueError(f'{args[0]} failed: {cp.stderr[-1500:]}')
    return cp


def probe_audio(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]).stdout)
    audio = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    if not audio:
        raise ValueError('download contains no audio stream')
    duration = float(data.get('format', {}).get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('audio has invalid duration')
    return duration


def prepare(args):
    project, record = Path(args.project).resolve(), Path(args.record).resolve()
    if record.exists():
        raise ValueError('MUSIC.json already exists; preserve it and use a new revision')
    if not project.is_dir():
        raise ValueError('scaffold project before preparing its music')
    # Refresh catalog and license evidence immediately before download.
    items = catalog(refresh=True)
    track = next((item for item in items if item.get('isrc') == args.id), None)
    if not track:
        raise ValueError('selected track no longer exists in the public catalog')
    if vocal_declaration(track):
        raise ValueError('track metadata declares vocals; choose an instrumental')
    evidence = fetch(PAGE, max_bytes=2 * 1024 * 1024).decode('utf-8')
    if 'creativecommons.org/licenses/by/4.0/' not in evidence or 'Attribution Code' not in evidence or 'Kevin MacLeod' not in evidence:
        raise ValueError('current provider page no longer verifies expected CC BY 4.0 attribution; review terms manually')
    filename = track.get('filename', '')
    if not filename or Path(filename).name != filename or not filename.lower().endswith('.mp3'):
        raise ValueError('invalid catalog filename')
    url = 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/' + urllib.parse.quote(filename)
    folder = project/'assets/audio/music'/args.id.lower()
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'license-evidence.html').write_text(evidence)
    write_json(folder/'catalog-record.json', track)
    original, bed = folder/'original.mp3', folder/'bed.wav'
    fetch(url, original)
    original_duration = probe_audio(original)
    if args.start + args.duration > original_duration + .05:
        raise ValueError('chosen source interval does not cover edit; choose another interval/track, never silently loop')
    fade_out = min(.45, args.duration / 4)
    filters = f'loudnorm=I=-20:TP=-3:LRA=7,afade=t=in:d={min(.12, args.duration/4)},afade=t=out:st={args.duration-fade_out}:d={fade_out}'
    run(['ffmpeg', '-nostdin', '-n', '-v', 'error', '-ss', str(args.start), '-i', str(original),
         '-t', str(args.duration), '-vn', '-af', filters, '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(bed)])
    duration = probe_audio(bed)
    if abs(duration - args.duration) > .05:
        raise ValueError('prepared music duration does not match the edit')
    run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(bed), '-f', 'null', '-'])
    analysis = run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(bed), '-af',
                    'loudnorm=I=-20:TP=-3:LRA=7:print_format=json', '-f', 'null', '-']).stderr
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', analysis)
    if not blocks or not math.isfinite(float(json.loads(blocks[-1])['input_i'])):
        raise ValueError('prepared bed is silent or unmeasurable')
    integrated = float(json.loads(blocks[-1])['input_i'])
    if integrated <= -50:
        raise ValueError('prepared bed is effectively silent')
    # Only metadata/measurement selection is possible without auditioning; never claim a listen.
    catalog_hash = sha(folder/'catalog-record.json')
    evidence_hash = sha(folder/'license-evidence.html')
    title = str(track['title'])
    attribution = (f'"{title}" by Kevin MacLeod (incompetech.com)\nSource: {url}\n'
                   f'Licensed under Creative Commons Attribution 4.0 International: {LICENSE}\n'
                   f'Changes: excerpt from {args.start:g}s; trimmed to {args.duration:g}s, fades and level adjustment.\n')
    (folder/'ATTRIBUTION.txt').write_text(attribution)
    data = {'status': 'ready', 'provider': 'incompetech', 'query': args.query, 'choice_reason': args.reason,
            'selected_at': now(), 'track_id': args.id, 'title': title, 'artist': 'Kevin MacLeod',
            'source_url': PAGE, 'download_url': url, 'license': 'CC BY 4.0', 'license_url': LICENSE,
            'license_evidence': {'page': PAGE, 'retrieved_at': now(), 'sha256': evidence_hash,
                                 'file': str((folder/'license-evidence.html').relative_to(project)),
                                 'statement': 'Provider catalog declares Kevin MacLeod tracks under Creative Commons By Attribution 4.0.'},
            'catalog_record': {'path': str((folder/'catalog-record.json').relative_to(project)),
                               'sha256': catalog_hash},
            'original': {'path': str(original.relative_to(project)), 'sha256': sha(original), 'duration': original_duration},
            'asset': {'path': str(bed.relative_to(project)), 'sha256': sha(bed), 'duration': duration,
                      'integrated_lufs': integrated},
            'source_start': args.start, 'duration': args.duration, 'attribution': attribution,
            'attribution_file': str((folder/'ATTRIBUTION.txt').relative_to(project)), 'timeline_id': 'bgm-bed',
            'instrumental_status': 'metadata-inferred; not auditioned',
            'review_note': 'Matched by catalog metadata; inspect available playback/measurements before final mix.'}
    data['identity'] = identity(data)
    write_json(record, data)
    return data


IDENTITY_FIELDS = ('provider', 'track_id', 'title', 'artist', 'license', 'license_url',
                   'attribution', 'asset', 'original', 'license_evidence', 'catalog_record', 'duration')


def identity(record):
    payload = {key: record.get(key) for key in IDENTITY_FIELDS if key in record}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def mean_level(path):
    cp = run(['ffmpeg', '-nostdin', '-hide_banner', '-t', '30', '-i', str(path),
              '-af', 'volumedetect', '-f', 'null', '-'], timeout=60)
    match = re.search(r'mean_volume:\s*(-?\d+(?:\.\d+)?) dB', cp.stderr)
    return float(match.group(1)) if match else math.nan


def project_file(project, relative):
    path = (project / str(relative)).resolve()
    if not path.is_relative_to(project.resolve()) or not path.is_file():
        raise ValueError(f'music provenance file is missing/outside project: {relative}')
    return path


def check_music(root, timeline=None):
    root = Path(root).resolve()
    expected = json.loads((root/'DELIVERY.json').read_text())
    if expected.get('expect_music') is not True:
        return {'status': 'not_required'}
    record_path = root/'MUSIC.json'
    if not record_path.is_file():
        raise ValueError('required background music has not been selected/prepared')
    music = json.loads(record_path.read_text())
    if music.get('status') != 'ready' or not str(music.get('choice_reason', '')).strip():
        raise ValueError('required background music has not been selected/prepared')
    asset = music.get('asset', {})
    project = root/'project'
    path = project_file(project, asset.get('path'))
    if sha(path) != asset.get('sha256'):
        raise ValueError('music asset is missing/changed/outside project')
    if music.get('license') not in APPROVED_LICENSES:
        raise ValueError('music reuse license is not approved')
    if not music.get('license_url') or not music.get('attribution') or not music.get('license_evidence'):
        raise ValueError('missing music license evidence/attribution')
    if mean_level(path) <= -50:
        raise ValueError('music bed is effectively silent')
    if abs(float(asset['duration']) - float(expected['duration'])) > .1:
        raise ValueError('music bed duration no longer matches edit')
    if music.get('provider') == 'incompetech':
        if music.get('identity') != identity(music):
            raise ValueError('music identity changed after preparation')
        evidence = music['license_evidence']
        evidence_file = project_file(project, evidence.get('file'))
        if sha(evidence_file) != evidence.get('sha256'):
            raise ValueError('saved license evidence no longer matches its hash')
        catalog = music.get('catalog_record') or {}
        if sha(project_file(project, catalog.get('path'))) != catalog.get('sha256'):
            raise ValueError('saved catalog record no longer matches its hash')
        original = music.get('original') or {}
        if sha(project_file(project, original.get('path'))) != original.get('sha256'):
            raise ValueError('original download no longer matches its hash')
        credits = project_file(project, music.get('attribution_file'))
        if credits.read_text().strip() != str(music['attribution']).strip():
            raise ValueError('attribution file no longer matches MUSIC.json')
    if timeline is not None:
        tracks = timeline.get('timeline', {}).get('tracks')
        if not isinstance(tracks, list):
            raise ValueError('invalid HyperFrames timeline JSON')
        rows = [row for track in tracks for row in track.get('rows', []) if isinstance(row, dict)]
        matches = [row for row in rows if row.get('id') == music.get('timeline_id')]
        if not matches:
            raise ValueError('downloaded music is not mounted as the bgm-bed audio clip')
        if any(row.get('src') != asset['path'] or row.get('kind') != 'audio' for row in matches):
            raise ValueError('bgm-bed id is used by a different source clip')
        row = matches[0]
        duration = float(expected['duration'])
        if row.get('pendingReason') or row.get('laneError'):
            raise ValueError('bgm-bed has unresolved timing or unreadable automation')
        rate = row.get('playbackRate')
        if rate not in (None, 1, 1.0):
            raise ValueError('bgm-bed playback rate is changed')
        media_start = float(row.get('mediaStart') or 0)
        if abs(media_start) > .05:
            raise ValueError('bgm-bed source offset does not match the prepared bed')
        if float(row.get('absStart', 999)) > .1 or float(row.get('absEnd', 0)) < duration - .1:
            raise ValueError('background-music timeline clip does not cover the edit')
        if abs(float(row.get('duration', 0)) - duration) > .1:
            raise ValueError('background-music timeline clip duration does not match the edit')
        base = row.get('volume')
        base = 1.0 if base is None else float(base)
        if not math.isfinite(base) or base <= 0:
            raise ValueError('background-music timeline clip has zero/invalid gain')
        points = []
        for lane in row.get('lanes') or []:
            if lane.get('target') == 'volume':
                for point in lane.get('points') or []:
                    value = float(point.get('v'))
                    if not math.isfinite(value):
                        raise ValueError('background-music volume automation is invalid')
                    points.append(value)
        if base * (max(points) if points else 1) <= .02:
            raise ValueError('background-music volume automation mutes the bed for the whole edit')
    return {'status': 'ready', 'sha256': asset['sha256'], 'identity': music.get('identity'),
            'track_id': music.get('track_id'), 'asset': asset['path'],
            'audibility': 'bed level and timeline gain/automation checked; no isolated music stem rendered',
            'attribution': music['attribution']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest='command', required=True)
    search = subs.add_parser('search', help='rank public catalog metadata after understanding the footage')
    search.add_argument('--query', required=True)
    search.add_argument('--duration', required=True, type=float)
    search.add_argument('--bpm-min', type=float, default=0)
    search.add_argument('--bpm-max', type=float, default=250)
    search.add_argument('--limit', type=int, default=6)
    search.add_argument('--output')
    prep = subs.add_parser('prepare', help='verify license, download one selected track and prepare a local bed')
    for name in ('id', 'query', 'reason', 'project', 'record'):
        prep.add_argument('--'+name, required=True)
    prep.add_argument('--duration', required=True, type=float)
    prep.add_argument('--start', type=float, default=0)
    check = subs.add_parser('check', help='verify required music and optional HyperFrames timeline JSON')
    check.add_argument('--root', required=True)
    check.add_argument('--timeline')
    args = ap.parse_args()
    try:
        if args.command in {'search', 'prepare'}:
            if not math.isfinite(args.duration) or not 0 < args.duration <= 600:
                raise ValueError('duration must be positive, finite and at most 600 seconds')
        if args.command == 'search':
            result = {'query': args.query, 'provider': 'incompetech', 'retrieved_at': now(),
                      'results': rank(catalog(), args.query, args.duration, args.bpm_min, args.bpm_max)[:max(1, min(10, args.limit))]}
            if args.output:
                write_json(args.output, result)
        elif args.command == 'prepare':
            if not re.fullmatch(r'[A-Za-z0-9]{8,20}', args.id) or not math.isfinite(args.start) or args.start < 0 or not args.reason.strip():
                raise ValueError('invalid track ID, interval or empty choice reason')
            result = prepare(args)
        else:
            timeline = json.loads(Path(args.timeline).read_text()) if args.timeline else None
            result = check_music(args.root, timeline)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
