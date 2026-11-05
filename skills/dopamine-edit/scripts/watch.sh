#!/usr/bin/env bash
# dopamine-edit — optional folder watcher.
# Watches raw/ and starts an OpenCode session when new footage lands.
# Not installed by default: it spends tokens without a human present.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="${DOPAMINE_ROOT:-$HOME/Work/video_editing}"
RAW="$PROJECT_ROOT/raw"
STATE_DIR="${DOPAMINE_STATE_DIR:-$HOME/.config/dopamine-edit}"
LOCK="$STATE_DIR/watch.lock"
LOG="$STATE_DIR/watch.log"
UNIT_DIR="${HOME}/.config/systemd/user"
UNIT="$UNIT_DIR/dopamine-edit-watch.service"

usage() {
  cat <<EOF
Usage: watch.sh [--foreground | --install-service | --uninstall-service | --status]

  --foreground         Watch raw/ in this terminal (default).
  --install-service    Install and start a systemd --user service.
  --uninstall-service  Stop and remove the service.
  --status             Show service status.

Environment:
  DOPAMINE_ROOT        Default: $PROJECT_ROOT
  DOPAMINE_DEBOUNCE    Seconds to wait after the last file event (default: 15)

The watcher uses normal OpenCode permissions, NOT --auto. Configure any required
unattended permissions separately; installing this service does not grant them.
EOF
}

install_service() {
  command -v systemctl >/dev/null 2>&1 || { echo "systemctl not found" >&2; exit 1; }
  mkdir -p "$UNIT_DIR"
  python3 - "$UNIT" "$SKILL_DIR" "$PROJECT_ROOT" "$STATE_DIR" <<'PY'
import os, sys
from pathlib import Path
unit, skill, root, state = sys.argv[1:]
def quote(value):
    if '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('invalid newline/NUL in service value')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
values = {'DOPAMINE_ROOT': root, 'DOPAMINE_STATE_DIR': state}
for key in ('DOPAMINE_DEBOUNCE', 'DOPAMINE_HF_VERSION', 'DOPAMINE_CACHE_DIR'):
    if key in os.environ:
        values[key] = os.environ[key]
lines = ['[Unit]', 'Description=Dopamine Edit raw-folder watcher', 'After=default.target', '',
         '[Service]', 'Type=simple', f'ExecStart={quote(skill + "/scripts/watch.sh")} --foreground',
         'Restart=on-failure', 'RestartSec=10']
lines += ['Environment=' + quote(k+'='+v) for k,v in values.items()]
lines += ['WorkingDirectory='+quote(root), '', '[Install]', 'WantedBy=default.target', '']
Path(unit).write_text('\n'.join(lines))
PY
  systemctl --user daemon-reload
  systemctl --user enable --now dopamine-edit-watch.service
  echo "installed: $UNIT"
  echo "logs:      journalctl --user -u dopamine-edit-watch -f"
}

uninstall_service() {
  systemctl --user disable --now dopamine-edit-watch.service 2>/dev/null || true
  rm -f "$UNIT"
  systemctl --user daemon-reload 2>/dev/null || true
  echo "removed: $UNIT"
}

status_service() {
  systemctl --user status dopamine-edit-watch.service --no-pager || true
}

watch_foreground() {
  command -v inotifywait >/dev/null 2>&1 || {
    echo "ERROR: inotifywait not found." >&2
    echo "Install: sudo pacman -S inotify-tools   (or: sudo apt install inotify-tools)" >&2
    exit 1
  }
  command -v opencode >/dev/null 2>&1 || { echo "ERROR: opencode not found" >&2; exit 1; }
  command -v flock >/dev/null 2>&1 || { echo 'ERROR: flock not found' >&2; exit 1; }
  mkdir -p "$STATE_DIR" "$RAW"
  # Kernel-managed process lock; no stale sentinel file after a crash.
  exec 9>"$LOCK"
  flock -n 9 || { echo 'ERROR: watcher already running' >&2; exit 1; }

  echo "watching $RAW"
  echo "debounce: ${DOPAMINE_DEBOUNCE:-15}s"
  echo "log: $LOG"

  inotifywait -m -r -e close_write,moved_to,create --format '%w%f' "$RAW" 2>/dev/null |
  while IFS= read -r path; do
    case "${path,,}" in
      *.mp4|*.mov|*.m4v|*.mkv|*.webm|*.avi|*.mts|*.m2ts|*.mpg|*.mpeg|*.wmv|*.flv|*.3gp|*.ogv)
        ;;
      *) continue ;;
    esac

    # Debounce: wait for the copy to settle, then process the batch once.
    sleep "${DOPAMINE_DEBOUNCE:-15}"

    if [ ! -f "$path" ] || [ ! -s "$path" ]; then
      continue
    fi
    before="$(stat -c '%s:%Y' -- "$path")"
    sleep 2
    if [ ! -f "$path" ] || [ "$before" != "$(stat -c '%s:%Y' -- "$path")" ]; then
      echo "$(date -Is) source still changing; leaving pending: $path" >> "$LOG"
      continue
    fi

    echo "$(date -Is) new footage: $path" >> "$LOG"
    if command -v notify-send >/dev/null 2>&1; then
      notify-send "Dopamine Edit" "New footage detected — starting the edit." || true
    fi

    (
      cd "$PROJECT_ROOT"
      opencode run --title "Dopamine edit $(date +%H:%M)" \
        "New footage landed in $RAW. Run the dopamine-edit skill now: bootstrap if needed, scan raw/, analyze each pending clip, pick template parents, matte the subject, build and render the edit. Work end to end without asking questions. Report every delivered file." \
        >> "$LOG" 2>&1
    ) || echo "$(date -Is) opencode run failed" >> "$LOG"

    echo "$(date -Is) run finished" >> "$LOG"
  done
}

case "${1:---foreground}" in
  --foreground) watch_foreground ;;
  --install-service) install_service ;;
  --uninstall-service) uninstall_service ;;
  --status) status_service ;;
  -h|--help) usage ;;
  *) usage; exit 2 ;;
esac
