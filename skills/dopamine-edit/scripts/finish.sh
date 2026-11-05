#!/usr/bin/env bash
# Render/check an isolated candidate. Human/model evidence review is separate.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SKILL_DIR/scripts/hf.sh"
usage() {
  echo 'Usage: finish.sh <project-dir> <slug> [--draft] [--json]'
  echo 'Requires ../DELIVERY.json. No check/snapshot bypasses. Success = candidate, not delivery.'
}
case "${1:-}" in -h|--help) usage; exit 0 ;; esac
[ $# -ge 2 ] || { usage; exit 2; }
PROJECT="$1" SLUG="$2"
shift 2
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo 'ERROR: unsafe slug' >&2; exit 2; }
QUALITY=delivery
for arg in "$@"; do
  case "$arg" in
    --draft) QUALITY=draft ;;
    --json) ;; # stdout is always a single JSON result; status messages go to stderr.
    *) echo "ERROR: unsupported option $arg (delivery gates cannot be bypassed)" >&2; exit 2 ;;
  esac
done
for cmd in python3 ffprobe ffmpeg npx; do
  command -v "$cmd" >/dev/null || { echo "ERROR: missing $cmd" >&2; exit 1; }
done
PROJECT="$(cd "$PROJECT" && pwd)"
OUT="$(cd "$PROJECT/.." && pwd)"
EXPECT="$OUT/DELIVERY.json"
python3 - "$SKILL_DIR/scripts" "$EXPECT" "$OUT/SOURCE.json" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verify_render import expectations
from scan_raw import validate_source_record
from music import check_music
expectations(Path(sys.argv[2]))
validate_source_record(Path(sys.argv[3]))
check_music(Path(sys.argv[2]).parent)
PY
mkdir -p "$OUT/final"
ATTEMPT="$(mktemp -d "$OUT/final/attempt-XXXXXXXX")"
LOG="$ATTEMPT/render.log"
VIDEO="$ATTEMPT/$SLUG.mp4"
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "ERROR: candidate not accepted (exit $status). Evidence: $ATTEMPT; inspect render.log and *-qa.json" >&2; fi' EXIT
cd "$PROJECT"
"${HF[@]}" timeline --json > "$ATTEMPT/timeline.json" 2> "$LOG"
python3 "$SKILL_DIR/scripts/music.py" check --root "$OUT" --timeline "$ATTEMPT/timeline.json" > "$ATTEMPT/music-check.json"
echo "Checking composition; evidence: $ATTEMPT" >&2
"${HF[@]}" check --json --snapshots > "$ATTEMPT/check.json" 2>> "$LOG"
python3 - "$ATTEMPT/check.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if d.get('ok') is not True or d.get('browserSkipped') is not False:
    raise SystemExit('ERROR: composition check failed or browser audit was skipped')
for section in ('lint', 'runtime', 'layout', 'contrast', 'audio'):
    if not isinstance(d.get(section), dict) or d[section].get('ok') is not True:
        raise SystemExit(f'ERROR: missing/failed {section} audit')
for section in ('layout', 'contrast'):
    samples = d[section].get('samples')
    if not isinstance(samples, list) or not samples:
        raise SystemExit(f'ERROR: {section} browser audit sampled no frames')
if d['contrast'].get('enabled') is not True:
    raise SystemExit('ERROR: contrast audit was disabled')
PY
"${HF[@]}" snapshot --frames 9 --output "$ATTEMPT/proof" >> "$LOG" 2>&1
python3 - "$ATTEMPT/proof" <<'PY'
import sys
from pathlib import Path
frames = [p for p in Path(sys.argv[1]).rglob('*.png') if p.is_file() and p.stat().st_size]
if len(frames) < 9:
    raise SystemExit('ERROR: snapshot returned fewer than nine proof PNGs')
PY
echo "Rendering $QUALITY candidate" >&2
"${HF[@]}" render -o "$VIDEO" --quality "$QUALITY" --skill dopamine-edit --strict >> "$LOG" 2>&1
QA="$ATTEMPT/$SLUG-qa.json"
python3 "$SKILL_DIR/scripts/verify_render.py" "$VIDEO" --expect "$EXPECT" \
  --report "$QA" --proof-dir "$ATTEMPT/decoded" > "$ATTEMPT/verification.json"
python3 - "$QA" "$QUALITY" "$OUT" "$SLUG" "$SKILL_DIR/scripts" <<'PY'
import json, os, shutil, sys
from pathlib import Path
qa, quality, root, slug = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, sys.argv[5])
from scan_raw import validate_source_record
from music import check_music
d = json.loads(qa.read_text())
d['source'] = validate_source_record(root/'SOURCE.json')
d['music'] = check_music(root, json.loads((qa.parent/'timeline.json').read_text()))
d['quality'] = quality
d['status'] = 'candidate_awaiting_review'
d['composition_check'] = str(qa.parent/'check.json')
d['composition_proof'] = str(qa.parent/'proof')
qa.write_text(json.dumps(d, indent=2) + '\n')
if quality == 'delivery':
    final = root/'final'
    targets = [final/f'{slug}.mp4', final/f'{slug}-cover.jpg', final/f'{slug}-contact.jpg', final/f'{slug}-qa.json']
    if any(p.exists() for p in targets):
        print(f'Existing output preserved; returning fresh attempt candidate at {qa.parent}', file=sys.stderr)
    else:
        # Exclusive creation: never clobber an output from a concurrent run.
        for source, target in zip([d['video'], d['cover'], d['contact']], targets[:3]):
            with open(source, 'rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
        d['video'], d['cover'], d['contact'] = map(str, targets[:3])
        with targets[3].open('x') as dst:
            json.dump(d, dst, indent=2)
            dst.write('\n')
        qa = targets[3]
if d['music'].get('status') == 'ready':
    credit_path = qa.parent/f'{slug}-music-credits.txt'
    if not credit_path.exists():
        credit_path.write_text(d['music']['attribution'])
    d['music_credits'] = str(credit_path)
    qa.write_text(json.dumps(d, indent=2) + '\n')
print(json.dumps({'status': d['status'], 'video': d['video'], 'cover': d['cover'],
                  'contact': d['contact'], 'qa': str(qa), 'quality': quality,
                  'music_credits': d.get('music_credits')}, indent=2))
PY
