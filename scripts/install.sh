#!/usr/bin/env bash
# Install only this repository's custom skill; no models, account changes or jobs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_ROOT="${DOPAMINE_SKILLS_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills}"
case "${1:-}" in
  '' ) ;;
  --help|-h) echo 'Usage: install.sh (DOPAMINE_SKILLS_DIR overrides destination)'; exit 0 ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac
python3 - "$ROOT/skills/dopamine-edit" "$DEST_ROOT/dopamine-edit" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import shutil, sys
source, target = map(lambda s: Path(s).expanduser().resolve(), sys.argv[1:])
if not (source/'SKILL.md').is_file():
    raise SystemExit('Repository skill source is missing')
if source == target or source.is_relative_to(target) or target.is_relative_to(source):
    raise SystemExit('Refusing overlapping source and destination')
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists():
    backup = Path.home()/'.local/state/dopamine-edit/install-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    shutil.copytree(target, backup, symlinks=True)
    print('Existing skill backed up:', backup)
shutil.copytree(source, target, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
print('Installed:', target)
print('No dependency installs, credentials, raw footage or watcher services were changed.')
PY
