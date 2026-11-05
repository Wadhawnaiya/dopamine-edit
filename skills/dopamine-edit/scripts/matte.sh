#!/usr/bin/env bash
# dopamine-edit — matte a subject with HyperFrames' local background removal.
# Produces subject.webm (foreground) + plate.webm (inverse-alpha plate).
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SKILL_DIR/scripts/hf.sh"

usage() {
  cat <<'EOF'
Usage: matte.sh <input-video> <outdir> [options]

  --quality fast|balanced|best   VP9 encoder quality (default: best)
  --device auto|cpu|coreml|cuda  Inference provider (default: auto)
  --no-plate                     Do not write plate.webm
  --force                        Re-run even if outputs are fresh
  --info                         Print detected providers and exit
  --json                         Print the final JSON record

Outputs:
  <outdir>/subject.webm   subject opaque, background transparent
  <outdir>/plate.webm     background opaque, subject hole transparent
  <outdir>/poster.jpg     first frame of the subject layer
  <outdir>/matte.json     result record
EOF
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --info) exec "${HF[@]}" remove-background --info ;;
esac
[ $# -lt 2 ] && { usage; exit 2; }

INPUT="$1"; shift
OUTDIR="$1"; shift

QUALITY="best"
DEVICE="auto"
PLATE=1
FORCE=0
JSON=0
INFO=0

while [ $# -gt 0 ]; do
  case "$1" in --quality|--device)
    [ $# -ge 2 ] && [[ "$2" != --* ]] || { echo "ERROR: $1 needs a value" >&2; exit 2; } ;;
  esac
  case "$1" in
    --quality) QUALITY="${2:-}"; shift 2 ;;
    --device) DEVICE="${2:-}"; shift 2 ;;
    --no-plate) PLATE=0; shift ;;
    --force) FORCE=1; shift ;;
    --json) JSON=1; shift ;;
    --info) INFO=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done
case "$QUALITY" in fast|balanced|best) ;; *) echo 'ERROR: invalid quality' >&2; exit 2 ;; esac
case "$DEVICE" in auto|cpu|coreml|cuda) ;; *) echo 'ERROR: invalid device' >&2; exit 2 ;; esac

for cmd in ffmpeg ffprobe npx; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing $cmd" >&2; exit 1; }
done

[ -f "$INPUT" ] || { echo "ERROR: input not found: $INPUT" >&2; exit 2; }
mkdir -p "$OUTDIR"
INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
OUTDIR="$(cd "$OUTDIR" && pwd)"

if [ "$INFO" -eq 1 ]; then
  exec "${HF[@]}" remove-background --info
fi

SUBJECT="$OUTDIR/subject.webm"
PLATE_OUT="$OUTDIR/plate.webm"
RECORD="$OUTDIR/matte.json"

if [ "$FORCE" -eq 0 ] && [ -s "$SUBJECT" ] && [ "$SUBJECT" -nt "$INPUT" ] &&
   { [ "$PLATE" -eq 0 ] || { [ -s "$PLATE_OUT" ] && [ "$PLATE_OUT" -nt "$INPUT" ]; }; } &&
   python3 - "$RECORD" "$INPUT" "$QUALITY" "$DEVICE" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    ok = d.get('source') == sys.argv[2] and d.get('quality') == sys.argv[3] and d.get('device') == sys.argv[4]
    ok = ok and d.get('subject_alpha_mode') is True
except (OSError, ValueError):
    ok = False
sys.exit(0 if ok else 1)
PY
then
  echo "matte: up to date -> $SUBJECT"
  [ "$JSON" -eq 1 ] && python3 - "$RECORD" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
print(p.read_text() if p.exists() else "{}")
PY
  exit 0
fi

echo "matte: $INPUT"
echo "       quality=$QUALITY device=$DEVICE plate=$PLATE"

ARGS=("${HF[@]}" remove-background "$INPUT"
  -o "$SUBJECT" --quality "$QUALITY" --device "$DEVICE" --json)
if [ "$PLATE" -eq 1 ]; then
  ARGS+=(--background-output "$PLATE_OUT")
fi

set +e
"${ARGS[@]}" 2>&1 | tee "$OUTDIR/matte.log"
STATUS=${PIPESTATUS[0]}
set -e

if [ "$STATUS" -ne 0 ] || [ ! -s "$SUBJECT" ]; then
  echo "ERROR: remove-background failed (exit $STATUS). See $OUTDIR/matte.log" >&2
  echo "Try: matte.sh \"$INPUT\" \"$OUTDIR\" --device cpu --force" >&2
  exit 3
fi
if [ "$PLATE" -eq 1 ] && [ ! -s "$PLATE_OUT" ]; then
  echo 'ERROR: requested inverse-alpha plate is missing' >&2; exit 3
fi

# Poster from the first frame (alpha is flattened for the preview).
ffmpeg -y -hide_banner -loglevel error -i "$SUBJECT" -frames:v 1 -q:v 2 "$OUTDIR/poster.jpg" 2>/dev/null || true

sub_pix="$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=nw=1:nk=1 "$SUBJECT" 2>/dev/null || echo unknown)"
sub_alpha="$(ffprobe -v error -select_streams v:0 -show_entries stream_tags=ALPHA_MODE -of default=nw=1:nk=1 "$SUBJECT" 2>/dev/null || true)"
if [ "${sub_alpha:-0}" != '1' ]; then
  echo 'ERROR: subject output is missing alpha metadata; inspect decoded alpha before using it' >&2
  exit 3
fi
plate_pix=""
[ -f "$PLATE_OUT" ] && plate_pix="$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=nw=1:nk=1 "$PLATE_OUT" 2>/dev/null || echo unknown)"

python3 - "$RECORD" "$INPUT" "$SUBJECT" "$PLATE_OUT" "$QUALITY" "$DEVICE" "$sub_pix" "$plate_pix" "${sub_alpha:-0}" <<'PY'
import json, os, sys
from datetime import datetime, timezone
record, src, subj, plate, quality, device, sub_pix, plate_pix, alpha = sys.argv[1:10]
data = {
    "source": src,
    "subject": subj,
    "subject_pix_fmt": sub_pix,
    "subject_alpha_mode": str(alpha).strip() == "1",
    "subject_bytes": os.path.getsize(subj) if os.path.exists(subj) else 0,
    "plate": plate if os.path.exists(plate) else None,
    "plate_pix_fmt": plate_pix or None,
    "plate_bytes": os.path.getsize(plate) if os.path.exists(plate) else 0,
    "quality": quality,
    "device": device,
    "model": "u2net_human_seg",
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(record, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(json.dumps(data, indent=2))
PY

echo "matte: done"
echo "  subject: $SUBJECT (pix_fmt=$sub_pix, alpha_mode=${sub_alpha:-0})"
[ -f "$PLATE_OUT" ] && echo "  plate:   $PLATE_OUT ($plate_pix)"
echo "  poster:  $OUTDIR/poster.jpg"
echo "  record:  $RECORD"
