#!/usr/bin/env bash
# Read-only tool preflight by default; explicit flags opt into maintenance.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SKILL_DIR/scripts/hf.sh"
STATE_DIR="${DOPAMINE_STATE_DIR:-$HOME/.config/dopamine-edit}"
CACHE_DIR="${DOPAMINE_CACHE_DIR:-$HOME/.cache/dopamine-edit}"
REFS_DIR="$CACHE_DIR/awesome-opus5-5-videos"
UPDATE=0 REFRESH=0 QUIET=0
for arg in "$@"; do
  case "$arg" in
    --update) UPDATE=1 ;;
    --refresh-refs) REFRESH=1 ;;
    --no-update) UPDATE=0 ;;
    --force) echo 'ERROR: use explicit --update and/or --refresh-refs after authorization' >&2; exit 2 ;;
    --quiet) QUIET=1 ;;
    -h|--help)
      echo 'Usage: bootstrap.sh [--update] [--refresh-refs] [--quiet]'
      echo 'Default: check only. --update resolves latest CLI for this check (not a global upgrade).'
      echo 'Maintenance flags require user authorization.'
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
mkdir -p "$STATE_DIR" "$CACHE_DIR"
LOG="$STATE_DIR/bootstrap.log"
: > "$LOG"
say() { printf '%s\n' "$*" >> "$LOG"; [ "$QUIET" -eq 1 ] || printf '%s\n' "$*" >&2; }
missing=0
for cmd in ffmpeg ffprobe python3 node npx git timeout; do
  if command -v "$cmd" >/dev/null 2>&1; then say "ok: $cmd";
  else say "ERROR: required tool missing: $cmd"; missing=1; fi
done
[ "$missing" -eq 0 ] || exit 1
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' || {
  say 'ERROR: HyperFrames requires Node.js 22+'; exit 1;
}
for cmd in yt-dlp agent-reach whisper-cli; do
  if command -v "$cmd" >/dev/null 2>&1; then say "optional available: $cmd";
  else say "optional unavailable: $cmd (no automatic install)"; fi
done
if [ "$UPDATE" -eq 1 ]; then
  # Resolve a fresh cached CLI, not an interactive upgrade or all-skills update.
  HF=(npx hyperframes@latest)
  say 'Authorized latest-CLI check; no global upgrade or skill changes'
fi
HF_VERSION="$(timeout 90 "${HF[@]}" --version 2>>"$LOG")" || {
  say 'ERROR: HyperFrames CLI unavailable. Cached package may be absent; no global installation attempted.'
  exit 1
}
say "CLI: $HF_VERSION"
DOCTOR_STATUS=0
timeout 180 "${HF[@]}" doctor --json > "$STATE_DIR/doctor.json" 2>>"$LOG" || DOCTOR_STATUS=$?
if [ "$DOCTOR_STATUS" -ne 0 ]; then say "ERROR: doctor could not run ($DOCTOR_STATUS)"; exit 1; fi

if [ "$REFRESH" -eq 1 ]; then
  export GIT_TERMINAL_PROMPT=0
  if [ -d "$REFS_DIR/.git" ]; then
    if [ -n "$(git -C "$REFS_DIR" status --porcelain)" ]; then
      say 'WARN: template cache has local changes; leaving it untouched'
    elif timeout 180 git -C "$REFS_DIR" fetch --depth 1 origin main >> "$LOG" 2>&1; then
      timeout 60 git -C "$REFS_DIR" merge --ff-only FETCH_HEAD >> "$LOG" 2>&1 ||
        say 'WARN: cache diverged; preserving it (no reset)'
    else say 'WARN: refresh failed; using cached templates'; fi
  elif [ -e "$REFS_DIR" ]; then
    say 'WARN: template path already exists without git; preserving it'
  else
    timeout 300 git clone --depth 1 https://github.com/yihui-dev/awesome-opus5-5-videos.git \
      "$REFS_DIR" >> "$LOG" 2>&1 || say 'WARN: clone failed; use built-in style taxonomy'
  fi
fi
COMMIT="$(git -C "$REFS_DIR" rev-parse --short HEAD 2>/dev/null || true)"
python3 - "$STATE_DIR" "$CACHE_DIR" "$HF_VERSION" "$COMMIT" <<'PY'
import json, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
state, cache, version, commit = sys.argv[1:]
state = Path(state)
try:
    doctor = json.loads((state / 'doctor.json').read_text())
except (ValueError, OSError) as exc:
    raise SystemExit(f'ERROR: invalid doctor JSON: {exc}')
if not isinstance(doctor, dict) or not isinstance(doctor.get('ok'), bool):
    raise SystemExit('ERROR: doctor JSON missing boolean ok')
# Optional Docker/provider findings must not force unrelated installations.
required_findings = []
for check in doctor.get('checks', []):
    name = str(check.get('name', '')).casefold()
    if name in {'node.js', 'ffmpeg', 'ffprobe', 'chrome', 'disk'} and check.get('ok') is False:
        required_findings.append(check)
try:
    count = len(json.loads((Path(cache)/'awesome-opus5-5-videos/data/videos.json').read_text()))
except (ValueError, OSError):
    count = 0
data = {
    'last_check_at': datetime.now(timezone.utc).isoformat(),
    'hyperframes': version.strip(), 'refs_commit': commit or None, 'refs_count': count,
    'optional_tools': {n: shutil.which(n) for n in ('agent-reach', 'yt-dlp', 'whisper-cli')},
    'doctor_ok': doctor['ok'], 'required_findings': required_findings,
}
tmp = state / 'setup.json.tmp'
tmp.write_text(json.dumps(data, indent=2) + '\n')
os.replace(tmp, state / 'setup.json')
print(json.dumps(data, indent=2))
if required_findings:
    raise SystemExit('ERROR: required render dependencies failed; inspect doctor.json')
if not doctor['ok']:
    print('WARN: doctor has optional/unclassified findings; inspect before rendering', file=sys.stderr)
PY
