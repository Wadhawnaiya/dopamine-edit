#!/usr/bin/env python3
"""Scan the dopamine-edit raw folder for new or changed footage.

Read-only for the source folder. State is kept in
~/.config/dopamine-edit/processed.json so a clip is only edited once.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts",
    ".mpg", ".mpeg", ".wmv", ".flv", ".3gp", ".ogv",
}
DEFAULT_ROOT = Path.home() / 'Work/video_editing'
DEFAULT_STATE = Path(os.environ.get('DOPAMINE_STATE_DIR', str(Path.home() / '.config/dopamine-edit'))) / 'processed.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: Path, strict: bool = False) -> dict:
    if not path.exists():
        return {"sources": {}}
    try:
        with path.open() as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("state is not an object")
        data.setdefault("sources", {})
        if not isinstance(data['sources'], dict):
            raise ValueError('sources is not an object')
        return data
    except Exception as exc:  # noqa: BLE001 - a corrupt state must not block the run
        if strict:
            raise ValueError(f'corrupt state preserved at {path}: {exc}') from exc
        print(f"WARN: could not read {path}: {exc}; starting fresh", file=sys.stderr)
        return {"sources": {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name, suffix='.tmp', delete=False) as f:
        tmp = Path(f.name)
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def fingerprint(path: Path) -> str:
    """Cheap but stable: size + mtime + first/last 1 MiB hash."""
    st = path.stat()
    h = hashlib.sha1()
    with path.open("rb") as f:
        h.update(f.read(1024 * 1024))
        if st.st_size > 2 * 1024 * 1024:
            f.seek(-1024 * 1024, os.SEEK_END)
            h.update(f.read(1024 * 1024))
    return f"{st.st_size}:{st.st_mtime_ns}:{h.hexdigest()[:16]}"


def slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:80].rstrip('-')
    return slug or "clip"


def validate_delivery(output: Path, target: Path) -> dict:
    """Require evidence tied to this exact source and encode before marking done."""
    from verify_render import digest, expectations
    required = ('ANALYSIS.md', 'REFERENCES.md', 'STYLE.md', 'BRIEF.md', 'STORYBOARD.md', 'EDIT.md')
    for name in required:
        p = output / name
        if not p.is_file() or not p.stat().st_size:
            raise ValueError(f'missing planning artifact: {name}')
    expected = expectations(output / 'DELIVERY.json')
    review = json.loads((output/'REVIEW.json').read_text())
    if review.get('status') != 'passed':
        raise ValueError('review has not passed')
    checks = review.get('checks', {})
    if not all(checks.get(key) is True for key in ('visual', 'audio', 'captions', 'timing')):
        raise ValueError('incomplete visual/audio/caption/timing review')
    if not isinstance(review.get('evidence'), list) or not any(isinstance(e, str) and e.strip() for e in review['evidence']):
        raise ValueError('review needs inspection evidence')
    mode = review.get('audio_review')
    if mode not in {'measured', 'listened', 'silent'}:
        raise ValueError('audio_review must be measured, listened or silent')
    if mode == 'silent' and expected['expect_audio']:
        raise ValueError('silent review conflicts with required audio')
    if mode == 'measured' and not (
        isinstance(review.get('limitations'), list)
        and any(isinstance(e, str) and e.strip() for e in review['limitations'])
    ):
        raise ValueError('measured-only audio review must disclose listening limitation')
    video = (output / review['video']).resolve()
    if not video.is_relative_to((output/'final').resolve()) or not video.is_file():
        raise ValueError('review video must be an existing file inside output/final')
    qa = json.loads(video.with_name(video.stem + '-qa.json').read_text())
    if expected.get('expect_music') is True:
        from music import check_music
        music = check_music(output)
        if qa.get('music', {}).get('sha256') != music['sha256']:
            raise ValueError('music changed after verified render')
        if music.get('identity') and qa.get('music', {}).get('identity') != music['identity']:
            raise ValueError('music provenance changed after verified render')
        if not (output/'MUSIC.md').is_file():
            raise ValueError('missing footage-led music brief MUSIC.md')
    if qa.get('ok') is not True or qa.get('quality') != 'delivery':
        raise ValueError('delivery-quality automated QA has not passed')
    if Path(qa['video']).resolve() != video or qa.get('expected') != expected:
        raise ValueError('QA does not match video or current delivery expectations')
    sha = digest(video)
    if qa.get('sha256') != sha or review.get('sha256') != sha:
        raise ValueError('video changed since QA/review')
    source = validate_source_record(output/'SOURCE.json')
    if Path(source['path']).resolve() != target or any(
        item != source['fingerprint'] for item in (
            qa.get('source', {}).get('fingerprint'), review.get('source_fingerprint'), fingerprint(target)
        )
    ):
        raise ValueError('ingestion, QA, review and current raw fingerprint must match')
    return {'video': str(video), 'sha256': sha, 'review': str(output/'REVIEW.json')}


def validate_source_record(path: Path) -> dict:
    source = json.loads(path.read_text())
    target = Path(source['path']).resolve()
    if not target.is_file() or source.get('fingerprint') != fingerprint(target):
        raise ValueError('source changed since ingestion; use a new output revision')
    return source


def iter_videos(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not p.name.startswith("."):
            out.append(p)
    return out


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.environ.get('DOPAMINE_ROOT', str(DEFAULT_ROOT)), help="video_editing root")
    ap.add_argument("--state", default=str(DEFAULT_STATE), help="processed.json path")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--all", action="store_true", help="include already-processed files")
    ap.add_argument("--mark", help="mark this file as processed")
    ap.add_argument("--output", help="output directory recorded with --mark")
    ap.add_argument("--unmark", help="remove this file from the processed state")
    ap.add_argument('--record-source', help='capture immutable ingestion fingerprint before copying/building')
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    raw = root / "raw"
    reference = root / "reference"
    if args.record_source:
        target = Path(args.record_source).expanduser().resolve()
        if not target.is_file() or not target.is_relative_to(raw.resolve()) or not args.output:
            ap.error('--record-source requires a file under raw/ and --output')
        output = Path(args.output).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        record = output/'SOURCE.json'
        source = {'path': str(target), 'fingerprint': fingerprint(target), 'recorded_at': now_iso()}
        try:
            with record.open('x') as stream:
                json.dump(source, stream, indent=2)
                stream.write('\n')
        except FileExistsError:
            try:
                previous = validate_source_record(record)
                if previous['path'] != str(target):
                    raise ValueError('output belongs to another source')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f'ERROR: ingestion record preserved: {exc}', file=sys.stderr)
                return 2
            source = previous
        print(json.dumps(source, indent=2))
        return 0
    state_path = Path(args.state).expanduser()
    if args.mark or args.unmark:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_lock = state_path.with_suffix(state_path.suffix + '.lock').open('a')
        fcntl.flock(state_lock, fcntl.LOCK_EX)
    try:
        state = load_state(state_path, strict=bool(args.mark or args.unmark))
    except ValueError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2

    if args.unmark:
        target = str(Path(args.unmark).expanduser().resolve())
        state["sources"].pop(target, None)
        save_state(state_path, state)
        print(f"unmarked {target}")
        return 0

    if args.mark:
        target = Path(args.mark).expanduser().resolve()
        if not target.is_file() or not target.is_relative_to(raw.resolve()) or target.suffix.lower() not in VIDEO_EXTS:
            print(f"ERROR: not found: {target}", file=sys.stderr)
            return 2
        if not args.output:
            print('ERROR: --mark requires --output with passed QA and review', file=sys.stderr)
            return 2
        try:
            delivery = validate_delivery(Path(args.output).expanduser().resolve(), target)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'ERROR: cannot mark processed: {exc}', file=sys.stderr)
            return 2
        entry = {
            "fingerprint": fingerprint(target),
            "processed_at": now_iso(),
            "output": str(Path(args.output).expanduser().resolve()) if args.output else None,
            **delivery,
        }
        state["sources"][str(target)] = entry
        save_state(state_path, state)
        print(json.dumps({"marked": str(target), **entry}, indent=2))
        return 0

    pending, done = [], []
    for path in sorted(iter_videos(raw), key=lambda p: (p.stat().st_mtime_ns, str(p))):
        key = str(path.resolve())
        if not path.resolve().is_relative_to(raw.resolve()):
            continue
        fp = fingerprint(path)
        prev = state["sources"].get(key)
        recorded_video = Path(prev['video']) if prev and prev.get('video') else None
        output_missing = recorded_video is not None and (not recorded_video.is_file() or not recorded_video.stat().st_size)
        item = {
            "path": key,
            "name": path.name,
            "slug": slugify(path.stem) + '-' + hashlib.sha256(str(path.relative_to(raw)).encode()).hexdigest()[:8],
            "size": path.stat().st_size,
            "size_human": human_size(path.stat().st_size),
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "fingerprint": fp,
            "status": "done" if prev and prev.get("fingerprint") == fp and not output_missing else "pending",
            "reason": "recorded_delivery_missing" if output_missing else None,
            "processed_at": prev.get("processed_at") if prev else None,
            "output": prev.get("output") if prev else None,
        }
        (done if item["status"] == "done" else pending).append(item)

    refs = []
    for path in iter_videos(reference):
        refs.append({
            "path": str(path.resolve()),
            "name": path.name,
            "size_human": human_size(path.stat().st_size),
        })

    report = {
        "root": str(root),
        "raw": str(raw),
        "pending": pending,
        "done": done if args.all else [],
        "done_count": len(done),
        "reference": refs,
        "state": str(state_path),
        "scanned_at": now_iso(),
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"raw: {raw}")
    if not pending:
        print("pending: none")
    else:
        print(f"pending: {len(pending)}")
        for item in pending:
            print(f"  + {item['name']:<40} {item['size_human']:>8}  -> output/{item['slug']}")
    if done:
        print(f"already done: {len(done)} (use --all to list)")
    if refs:
        print(f"reference clips: {len(refs)} (style references, not edit targets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
