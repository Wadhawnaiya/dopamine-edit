#!/usr/bin/env python3
"""Install and verify the always-on brand layer for a dopamine-edit project.

The brand layer is the transparent cutout produced by brand-cutout.sh
(<skill>/assets/brand/logo.png). install copies it into the project and records
its hash; check proves the current project file, the skill asset and the
HyperFrames timeline agree before a candidate is accepted.
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

SKILL_DEFAULT = Path(__file__).resolve().parent.parent
PROJECT_REL = Path('assets/brand/logo.png')
ROW_ID = 'brand-layer'


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


def brand_dir(skill_dir: Path) -> Path:
    override = os.environ.get('DOPAMINE_BRAND_DIR')
    return Path(override).expanduser().resolve() if override else Path(skill_dir).resolve()/'assets/brand'


def skill_asset(skill_dir: Path) -> tuple[Path, dict]:
    folder = brand_dir(skill_dir)
    asset = folder/'logo.png'
    record = folder/'logo.json'
    if not asset.is_file():
        raise ValueError(f'brand cutout is missing ({asset}); run scripts/brand-cutout.sh <image> first')
    if not record.is_file():
        raise ValueError(f'brand record is missing ({record}); run scripts/brand-cutout.sh <image> first')
    meta = json.loads(record.read_text())
    if meta.get('asset_sha256') != sha(asset):
        raise ValueError('skill brand logo.png does not match its logo.json; rebuild the cutout')
    return asset, meta


def install(args) -> dict:
    project = Path(args.project).resolve()
    if not project.is_dir():
        raise ValueError('scaffold the project before installing the brand layer')
    asset, meta = skill_asset(Path(args.skill_dir).resolve())
    target = project/PROJECT_REL
    record = project/'assets/brand/BRAND.json'
    if target.is_file() and sha(target) != meta['asset_sha256']:
        raise ValueError('project brand layer differs from the skill asset; resolve it explicitly')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.read_bytes() != asset.read_bytes():
        target.write_bytes(asset.read_bytes())
    data = {'status': 'ready', 'path': PROJECT_REL.as_posix(),
            'asset_sha256': meta['asset_sha256'], 'width': meta.get('width'), 'height': meta.get('height'),
            'source': meta.get('source'), 'recipe_version': meta.get('recipe_version'),
            'installed_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            'timeline_id': ROW_ID}
    write_json(record, data)
    return data


def check(root, timeline=None, skill_dir=SKILL_DEFAULT) -> dict:
    root = Path(root).resolve()
    expected = json.loads((root/'DELIVERY.json').read_text())
    if expected.get('expect_brand') is not True:
        return {'status': 'not_required'}
    project = root/'project'
    target = (project/PROJECT_REL).resolve()
    if not target.is_relative_to(project.resolve()) or not target.is_file():
        raise ValueError('brand layer is not installed in the project')
    record = project/'assets/brand/BRAND.json'
    if not record.is_file():
        raise ValueError('brand layer has no BRAND.json; run scripts/brand.py install')
    data = json.loads(record.read_text())
    if data.get('status') != 'ready' or data.get('asset_sha256') != sha(target):
        raise ValueError('project brand layer changed after install')
    canonical = brand_dir(skill_dir)/'logo.png'
    if not canonical.is_file() or sha(canonical) != data['asset_sha256']:
        raise ValueError('project brand layer is not the current skill brand asset')
    if timeline is not None:
        tracks = timeline.get('timeline', {}).get('tracks')
        if not isinstance(tracks, list):
            raise ValueError('invalid HyperFrames timeline JSON')
        rows = [row for track in tracks for row in track.get('rows', []) if isinstance(row, dict)]
        matches = [row for row in rows if row.get('id') == ROW_ID]
        if not matches:
            raise ValueError(f'brand layer is not mounted as the {ROW_ID} clip')
        if any(row.get('src') != PROJECT_REL.as_posix() for row in matches):
            raise ValueError(f'{ROW_ID} id is used by a clip that is not the brand logo')
        row = matches[0]
        duration = float(expected['duration'])
        if row.get('pendingReason') or row.get('laneError'):
            raise ValueError('brand layer has unresolved timing or unreadable automation')
        if float(row.get('absStart', 999)) > .1 or float(row.get('absEnd', 0)) < duration - .1:
            raise ValueError('brand layer does not cover the whole edit')
    return {'status': 'ready', 'asset_sha256': data['asset_sha256'],
            'asset': PROJECT_REL.as_posix(), 'width': data.get('width'), 'height': data.get('height')}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest='command', required=True)
    inst = subs.add_parser('install', help='copy the skill brand cutout into a project')
    inst.add_argument('--project', required=True)
    inst.add_argument('--skill-dir', default=str(SKILL_DEFAULT))
    chk = subs.add_parser('check', help='verify installed brand layer and optional timeline use')
    chk.add_argument('--root', required=True)
    chk.add_argument('--timeline')
    chk.add_argument('--skill-dir', default=str(SKILL_DEFAULT))
    args = ap.parse_args()
    try:
        if args.command == 'install':
            result = install(args)
        else:
            timeline = json.loads(Path(args.timeline).read_text()) if args.timeline else None
            result = check(args.root, timeline, Path(args.skill_dir))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
