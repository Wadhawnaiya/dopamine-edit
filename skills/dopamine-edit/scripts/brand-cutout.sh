#!/usr/bin/env bash
# dopamine-edit — build the transparent brand-layer PNG from a neon/logo photo.
# Deterministic ImageMagick recipe (luminance x saturation alpha key), no models.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Recipe v1. Changing any value changes logo.json and invalidates projects.
RECIPE_VERSION="1"
LEVEL="28%,70%"
GAMMA="0.9"
BLUR="0x0.5"
MODULATE="105,130,100"
BORDER="24"

usage() {
  cat <<'EOF'
Usage: brand-cutout.sh <source-image> [--outdir DIR] [--force] [--json]

Removes the background of a bright subject (neon sign, logo) into a transparent
PNG by keying on luminance x saturation. The acrylic mount and tube glow are
kept; a busy/dark curtain like the source photo is removed.

  --outdir DIR   Output directory (default: <skill>/assets/brand)
  --force        Rebuild even when logo.json matches source and recipe
  --json         Print the final record

Outputs <outdir>/logo.png and <outdir>/logo.json (recipe + hashes + coverage).
The original image is never modified.
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac
[ $# -ge 1 ] || { usage; exit 2; }
SOURCE="$1"; shift
OUTDIR="${DOPAMINE_BRAND_DIR:-$SKILL_DIR/assets/brand}"
FORCE=0 JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --outdir) [ $# -ge 2 ] || { echo 'ERROR: --outdir needs a value' >&2; exit 2; }; OUTDIR="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --json) JSON=1; shift ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done
[ -f "$SOURCE" ] || { echo "ERROR: source image not found: $SOURCE" >&2; exit 2; }
command -v python3 >/dev/null || { echo 'ERROR: missing python3' >&2; exit 1; }
if ! command -v magick >/dev/null; then
  echo 'ERROR: ImageMagick 7 (magick) is required for brand-cutout.sh' >&2
  exit 1
fi

mkdir -p "$OUTDIR"
SOURCE="$(cd "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
OUTDIR="$(cd "$OUTDIR" && pwd)"
LOGO="$OUTDIR/logo.png"
RECORD="$OUTDIR/logo.json"

if [ "$FORCE" -eq 0 ] && [ -s "$LOGO" ] && python3 - "$RECORD" "$SOURCE" "$RECIPE_VERSION" <<'PY'
import hashlib, json, sys
try:
    d = json.load(open(sys.argv[1]))
    h = hashlib.sha256(open(sys.argv[2], 'rb').read()).hexdigest()
    ok = d.get('source_sha256') == h and str(d.get('recipe_version')) == sys.argv[3]
except (OSError, ValueError):
    ok = False
sys.exit(0 if ok else 1)
PY
then
  echo "brand-cutout: up to date -> $LOGO"
  [ "$JSON" -eq 1 ] && cat "$RECORD"
  exit 0
fi

echo "brand-cutout: $SOURCE"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dopamine-brand-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# score = luminance * saturation: neon tubes score high, a dark curtain low.
magick "$SOURCE" -colorspace gray -depth 8 "$WORK/luma.png"
magick "$SOURCE" -colorspace HSL -channel G -separate +channel -depth 8 "$WORK/sat.png"
magick "$WORK/luma.png" "$WORK/sat.png" -compose multiply -composite -depth 8 "$WORK/score.png"
magick "$WORK/score.png" -level "$LEVEL" -gamma "$GAMMA" -blur "$BLUR" -depth 8 "$WORK/alpha.png"
magick \( "$SOURCE" -modulate "$MODULATE" \) "$WORK/alpha.png" \
  -alpha off -compose CopyOpacity -composite -depth 8 "$WORK/cut.png"
magick "$WORK/cut.png" -trim +repage -bordercolor none -border "$BORDER" -strip -depth 8 "$LOGO"

python3 - "$SOURCE" "$LOGO" "$RECORD" "$RECIPE_VERSION" "$LEVEL" "$GAMMA" "$BLUR" "$MODULATE" "$BORDER" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
source, logo, record, version, level, gamma, blur, modulate, border = sys.argv[1:10]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def probe(p, entries):
    out = subprocess.run(['magick', 'identify', '-format', entries, str(p)],
                         capture_output=True, text=True, check=True).stdout.split()
    return out

width, height, channel_names = probe(logo, '%w %h %[channels]')[:3]
opaque = subprocess.run(['magick', 'identify', '-format', '%[opaque]', str(logo)],
                        capture_output=True, text=True, check=True).stdout.strip()
if 'a' not in channel_names:
    raise SystemExit('ERROR: produced logo has no alpha channel')
if opaque.lower() == 'true':
    raise SystemExit('ERROR: produced logo is fully opaque; background was not removed')
# Coverage: fraction of pixels with meaningful alpha.
frac = subprocess.run(['magick', str(logo), '-alpha', 'extract', '-threshold', '10%',
                       '-format', '%[fx:mean]', 'info:'], capture_output=True, text=True, check=True).stdout.strip()
coverage = float(frac)
if not 0.005 <= coverage <= 0.9:
    raise SystemExit(f'ERROR: suspicious alpha coverage {coverage:.3f}; inspect the source image')

data = {
    'asset': 'logo.png',
    'source': Path(source).name,
    'source_sha256': sha(source),
    'asset_sha256': sha(logo),
    'width': int(width),
    'height': int(height),
    'alpha_coverage': round(coverage, 4),
    'recipe_version': int(version),
    'recipe': {'tool': 'ImageMagick', 'level': level, 'gamma': gamma, 'blur': blur,
               'modulate': modulate, 'border': int(border), 'space': 'luma*saturation'},
    'tool_version': subprocess.run(['magick', '-version'], capture_output=True, text=True).stdout.splitlines()[0],
    'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'note': 'Background removed with a luminance x saturation key; acrylic mount and tube glow are part of the sign.',
}
Path(record).write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps(data, indent=2))
PY

echo "brand-cutout: done -> $LOGO"
