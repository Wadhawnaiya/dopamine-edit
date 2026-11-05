#!/usr/bin/env python3
"""Preview checkpoint: prove a draft was shown and approved before delivery.

Delivery renders must follow a preview the user saw. preview.py records the
draft, binds an approval to the exact composition digest, and verifies that
binding before a delivery render. The bypass is an explicit environment flag for
unattended runs (DOPAMINE_SKIP_PREVIEW=1).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

SOURCE_SUFFIXES = {'.html', '.css', '.js', '.mjs', '.cjs', '.ts', '.json'}
SKIP_DIRS = {'node_modules', 'assets', 'preview', 'final', '.git', '__pycache__'}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
        temp = stream.name
    os.replace(temp, path)


def digest(root: Path) -> str:
    """Hash the composition source + delivery plan; media and outputs excluded."""
    root = Path(root).resolve()
    entries: list[tuple[str, str]] = []
    candidates = []
    project = root/'project'
    if project.is_dir():
        for path in project.rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(project)
            if any(part in SKIP_DIRS for part in rel.parts) or path.suffix in ('.pyc',):
                continue
            if path.suffix in SOURCE_SUFFIXES:
                candidates.append(path)
    expected = root/'DELIVERY.json'
    if expected.is_file():
        candidates.append(expected)
    for path in sorted(set(candidates)):
        entries.append((str(path.relative_to(root)), sha(path)))
    payload = json.dumps(entries, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def relative(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value).resolve()
    try:
        return str(path.relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def load(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f'missing {path.name}')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f'invalid {path.name}')
    return data


def record(args) -> dict:
    root = Path(args.root).resolve()
    preview = root/'preview'
    for required in ('DELIVERY.json',):
        if not (root/required).is_file():
            raise ValueError(f'{required} is missing; plan the edit before previewing')
    video = Path(args.video).resolve()
    if not video.is_file() or video.stat().st_size == 0:
        raise ValueError('preview video is missing or empty')
    if video.parent == (root/'final').resolve():
        raise ValueError('preview must be a draft attempt, not a final delivery render')
    target = preview/f'{args.slug}-preview.mp4'
    preview.mkdir(parents=True, exist_ok=True)
    if video != target:
        target.write_bytes(video.read_bytes())
    data = {
        'status': 'awaiting_review', 'slug': args.slug, 'recorded_at': now(),
        'digest': digest(root), 'quality': 'draft',
        'video': relative(root, str(target)),
        'cover': relative(root, args.cover), 'contact': relative(root, args.contact),
        'qa': relative(root, args.qa), 'attempt': relative(root, args.attempt),
        'requested_changes': [],
        'how_to_review': [
            'Watch the draft MP4 end to end; it is a fast proxy of the final cut.',
            'Open the cover and contact sheet for framing, captions and matte edges.',
            'Open the Studio preview for an editable surface, or describe changes.',
            'Approval binds to the current composition; any edit needs a new preview.',
        ],
    }
    write_json(preview/'PREVIEW.json', data)
    return data


def approve(args) -> dict:
    root = Path(args.root).resolve()
    preview = load(root/'preview/PREVIEW.json')
    current = digest(root)
    changed = current != preview.get('digest')
    if changed and not args.force:
        raise ValueError('composition changed since the preview; re-run preview.sh before approving')
    data = {
        'status': 'approved', 'approved_at': now(), 'slug': preview.get('slug'),
        'digest': current,
        'preview_digest': preview.get('digest'),
        'changed_since_preview': changed,
        'note': (args.note or '').strip() or None,
        'approved_preview_video': preview.get('video'),
    }
    write_json(root/'preview/APPROVED.json', data)
    return data


def verify(root) -> dict:
    root = Path(root).resolve()
    preview_path, approved_path = root/'preview/PREVIEW.json', root/'preview/APPROVED.json'
    if not preview_path.is_file():
        return {'status': 'missing', 'detail': 'no preview recorded'}
    preview = json.loads(preview_path.read_text())
    if not approved_path.is_file():
        return {'status': 'awaiting_review', 'detail': 'preview recorded but not approved',
                'preview': preview.get('video')}
    approved = json.loads(approved_path.read_text())
    current = digest(root)
    if approved.get('digest') != current:
        return {'status': 'changed', 'detail': 'composition changed since approval; preview again'}
    return {'status': 'approved', 'slug': approved.get('slug'), 'video': preview.get('video'),
            'approved_at': approved.get('approved_at'), 'note': approved.get('note')}


def status(args) -> dict:
    root = Path(args.root).resolve()
    result = verify(root)
    result['digest'] = digest(root)
    for name in ('PREVIEW.json', 'APPROVED.json'):
        path = root/'preview'/name
        result[name] = json.loads(path.read_text()) if path.is_file() else None
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest='command', required=True)
    rec = subs.add_parser('record', help='record a shown draft as the pending preview')
    rec.add_argument('--root', required=True)
    rec.add_argument('--slug', required=True)
    rec.add_argument('--video', required=True)
    rec.add_argument('--cover')
    rec.add_argument('--contact')
    rec.add_argument('--qa')
    rec.add_argument('--attempt')
    app = subs.add_parser('approve', help='bind user approval to the current composition')
    app.add_argument('--root', required=True)
    app.add_argument('--note')
    app.add_argument('--force', action='store_true')
    ver = subs.add_parser('verify', help='report whether delivery is allowed')
    ver.add_argument('--root', required=True)
    sta = subs.add_parser('status', help='full preview/approval state for the user')
    sta.add_argument('--root', required=True)
    args = ap.parse_args()
    try:
        if args.command == 'record':
            result = record(args)
        elif args.command == 'approve':
            result = approve(args)
        elif args.command == 'verify':
            result = verify(Path(args.root))
        else:
            result = status(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
