#!/usr/bin/env bash
# dopamine-edit — pre-render preview checkpoint. Renders a fast draft, copies it
# to <output>/preview/ and records it for user review. Never writes to final/.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SKILL_DIR/scripts/hf.sh"

usage() {
  cat <<'EOF'
Usage: preview.sh <project-dir> <slug> [--json]

Renders a low-quality draft of the current composition and records it as the
pending preview. Show the draft, cover and contact sheet to the user, apply the
changes they ask for (preview again), then approve before a delivery render.

Writes only under <output>/preview/ (never final/ or state), so it is safe to run
repeatedly. Delivery renders stay blocked until an approval is bound to the same
composition, unless DOPAMINE_SKIP_PREVIEW=1 is set for an unattended run.
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac
[ $# -ge 2 ] || { usage; exit 2; }
PROJECT="$1" SLUG="$2"; shift 2
JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1; shift ;;
    --frames) [ $# -ge 2 ] || { echo 'ERROR: --frames needs a value' >&2; exit 2; }; shift 2 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo 'ERROR: unsafe slug' >&2; exit 2; }
for cmd in python3 npx; do
  command -v "$cmd" >/dev/null || { echo "ERROR: missing $cmd" >&2; exit 1; }
done
PROJECT="$(cd "$PROJECT" && pwd)"
OUT="$(cd "$PROJECT/.." && pwd)"
[ -f "$OUT/DELIVERY.json" ] || { echo "ERROR: $OUT/DELIVERY.json is missing; plan the edit first" >&2; exit 2; }

RESULT="$(mktemp "${TMPDIR:-/tmp}/dopamine-preview-XXXXXXXX.json")"
trap 'rm -f "$RESULT"' EXIT

echo "preview: rendering a draft (not a delivery)" >&2
if ! bash "$SKILL_DIR/scripts/finish.sh" "$PROJECT" "$SLUG" --draft --json > "$RESULT"; then
  echo "ERROR: draft preview failed; inspect the attempt directory under $OUT/final" >&2
  exit 1
fi

python3 - "$RESULT" "$OUT" "$SLUG" "$SKILL_DIR" "$PROJECT" "$JSON" "${HF[*]}" <<'PY'
import json, shutil, subprocess, sys
from pathlib import Path

result, out, slug, skill, project, want_json, studio = (
    Path(sys.argv[1]), Path(sys.argv[2]).resolve(), sys.argv[3],
    Path(sys.argv[4]), sys.argv[5], sys.argv[6] == '1', sys.argv[7])
data = json.loads(result.read_text())

video = Path(data['video']).resolve()
if not video.is_file() or video.stat().st_size == 0:
    raise SystemExit('ERROR: draft render produced no video')
if video.parent == (out/'final').resolve():
    raise SystemExit('ERROR: preview received a delivery render; refusing')

preview_dir = out/'preview'
preview_dir.mkdir(parents=True, exist_ok=True)
targets = {'video': preview_dir/f'{slug}-preview.mp4'}
sources = {'video': video}
for key in ('cover', 'contact'):
    value = data.get(key)
    if value and Path(value).is_file():
        sources[key] = Path(value)
        targets[key] = preview_dir/f'{slug}-{key}.jpg'
qa = Path(data['qa']).resolve()
sources['qa'], targets['qa'] = qa, preview_dir/f'{slug}-preview-qa.json'
for key, target in targets.items():
    temp = target.with_name(target.name + '.part')
    shutil.copyfile(sources[key], temp)
    temp.replace(target)

frames = qa.parent/'proof'
frame_dir = preview_dir/'frames'
if frames.is_dir():
    frame_dir.mkdir(exist_ok=True)
    for old in frame_dir.glob('*.png'):
        old.unlink()
    for png in sorted(frames.glob('*.png')):
        shutil.copyfile(png, frame_dir/png.name)

command = [sys.executable, str(skill/'scripts/preview.py'), 'record', '--root', str(out),
           '--slug', slug, '--video', str(targets['video']), '--qa', str(targets['qa'])]
if 'cover' in targets:
    command += ['--cover', str(targets['cover'])]
if 'contact' in targets:
    command += ['--contact', str(targets['contact'])]
record = subprocess.run(command, capture_output=True, text=True)
if record.returncode:
    sys.stderr.write(record.stderr)
    raise SystemExit('ERROR: could not record the preview')

summary = {
    'status': 'awaiting_review',
    'video': str(targets['video']),
    'cover': str(targets.get('cover')) if 'cover' in targets else None,
    'contact': str(targets.get('contact')) if 'contact' in targets else None,
    'qa': str(targets['qa']),
    'frames': str(frame_dir) if frames.is_dir() else None,
    'digest': json.loads(record.stdout)['digest'],
    'studio_command': f'{studio} preview {project}',
    'approve_command': f'python3 {skill}/scripts/preview.py approve --root {out}',
    'delivery_command': f'bash {skill}/scripts/finish.sh {project} {slug} --json',
    'note': 'Delivery renders are blocked until the user approves this composition.',
}
if want_json:
    print(json.dumps(summary, indent=2))
else:
    print('preview ready (awaiting review)')
    print(f"  video:   {summary['video']}")
    for key in ('cover', 'contact', 'frames'):
        if summary[key]:
            print(f"  {key + ':':<8} {summary[key]}")
    print(f"  studio:  {summary['studio_command']}")
    print('  show these to the user, collect changes, then approve:')
    print(f"    {summary['approve_command']}")
    print(f"  delivery: {summary['delivery_command']}")
PY
